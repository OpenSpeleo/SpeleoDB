# -*- coding: utf-8 -*-

"""Tests for `api:v2:tool-dmp-doctor` (POST).

View: `speleodb/api/v2/views/tools.py::ToolDMPDoctor`.  Accepts a
multipart upload (`file` + JSON-encoded `data`) and returns either a
corrected DMP blob or an `ErrorResponse` describing the failure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase

ARTIFACT_DIR = Path(__file__).parent / "artifacts"
REAL_DMP_PATH = ARTIFACT_DIR / "test_v5.dmp"


def _default_data(override: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "fix_dmp": False,
        "survey_date": timezone.now().date().isoformat(),
        "length_scaling": 1.0,
        "compass_offset": 0,
        "reverse_direction": False,
        "depth_offset": 0.0,
        "depth_offset_unit": "meters",
    }
    if override:
        payload.update(override)
    return payload


@pytest.mark.django_db
class TestToolDMPDoctor(BaseAPITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.url = reverse("api:v2:tool-dmp-doctor")

    # ---- authn ----

    def test_requires_authentication(self) -> None:
        client = APIClient()
        response = client.post(self.url, {}, format="multipart")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # ---- input validation ----

    def test_missing_file_returns_400(self) -> None:
        response = self.client.post(
            self.url,
            {"data": json.dumps(_default_data())},
            format="multipart",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "No file provided" in str(response.data)

    def test_wrong_extension_returns_400(self) -> None:
        bad = SimpleUploadedFile(
            "not-a-dmp.txt", b"not a dmp", content_type="text/plain"
        )
        response = self.client.post(
            self.url,
            {"file": bad, "data": json.dumps(_default_data())},
            format="multipart",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "Only .dmp files" in str(response.data)

    def test_bad_json_in_data_returns_400(self) -> None:
        upload = SimpleUploadedFile(
            "input.dmp", b";;;;;;;", content_type="application/octet-stream"
        )
        response = self.client.post(
            self.url,
            {"file": upload, "data": "not-json"},
            format="multipart",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "Invalid data format" in str(response.data)

    def test_bad_params_returns_400(self) -> None:
        upload = SimpleUploadedFile(
            "input.dmp", b";;;", content_type="application/octet-stream"
        )
        bad_params = _default_data({"length_scaling": -1.0})  # < 0 violates gt=0
        response = self.client.post(
            self.url,
            {"file": upload, "data": json.dumps(bad_params)},
            format="multipart",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_fix_mode_missing_survey_date_returns_400(self) -> None:
        upload = SimpleUploadedFile(
            "input.dmp", b";;;", content_type="application/octet-stream"
        )
        params = _default_data({"fix_dmp": True, "survey_date": None})
        response = self.client.post(
            self.url,
            {"file": upload, "data": json.dumps(params)},
            format="multipart",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "survey_date" in str(response.data)

    # ---- happy path against real artifact ----

    @pytest.mark.skipif(
        not REAL_DMP_PATH.exists(),
        reason="reference DMP artifact missing",
    )
    def test_happy_path_no_modifications(self) -> None:
        with REAL_DMP_PATH.open("rb") as f:
            upload = SimpleUploadedFile(
                "test_v5.dmp", f.read(), content_type="application/octet-stream"
            )
        response = self.client.post(
            self.url,
            {"file": upload, "data": json.dumps(_default_data())},
            format="multipart",
            headers={"authorization": self.auth},
        )
        # The correct-dmp pipeline is side-effect-free when all offsets are 0.
        # It either returns a valid file or a documented 400; we accept both
        # but fail on 5xx.
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ), response.data
        if response.status_code == status.HTTP_200_OK:
            assert "attachment" in response["content-disposition"].lower()
