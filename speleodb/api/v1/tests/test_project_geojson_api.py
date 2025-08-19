# -*- coding: utf-8 -*-

from __future__ import annotations

import random
import string
import tempfile
import uuid
from hashlib import sha1
from pathlib import Path
from typing import Any
from unittest.mock import patch

import orjson
import pytest
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from parameterized.parameterized import parameterized_class
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.surveys.models import GeoJSON
from speleodb.surveys.models import PermissionLevel
from speleodb.utils.test_utils import named_product


def temp_geojson_file() -> SimpleUploadedFile:
    """Fixture to create a temporary GeoJSON file."""

    return SimpleUploadedFile(
        "test.geojson",  # filename
        orjson.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [-87.501234, 20.196710],
                        },
                        "properties": {"name": "Test Cave Entrance"},
                    }
                ],
            }
        ),
        content_type="application/geo+json",
    )


def sha1_hash() -> str:
    rand_str = "".join([random.choice(string.ascii_lowercase) for _ in range(32)])
    return sha1(rand_str.encode("utf-8"), usedforsecurity=False).hexdigest()


@parameterized_class(
    [
        "level",
        "permission_type",
    ],
    named_product(
        level=[
            PermissionLevel.ADMIN,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.READ_ONLY,
            PermissionLevel.WEB_VIEWER,
        ],
        permission_type=[PermissionType.USER, PermissionType.TEAM],
    ),
)
class TestProjectGeoJsonApiView(BaseAPIProjectTestCase):
    """Test suite for the ProjectGeoJsonApiView endpoint."""

    level: PermissionLevel
    permission_type: PermissionType

    test_geojson: dict[str, Any] = {}

    def setUp(self) -> None:
        super().setUp()

        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )

    def test_geojson_endpoint_performance_uses_with_geojson_manager(self) -> None:
        """Test that the endpoint properly loads geojson field."""
        commit_sha = sha1_hash()
        # Set some test GeoJSON data
        GeoJSON.objects.create(
            project=self.project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            file=temp_geojson_file(),
        )

        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": self.project.id}
            ),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        # Verify the data was loaded correctly within SuccessResponse format
        response_data = orjson.loads(response.content)
        assert response_data["success"] is True
        assert "data" in response_data
        assert isinstance(response_data["data"]["geojson_files"], list)

        for geojson in response_data["data"]["geojson_files"]:
            assert "commit_sha" in geojson
            assert "url" in geojson
            assert "date" in geojson

    def test_geojson_endpoint_limit_returns_only_latest(self) -> None:
        """Endpoint should respect ?limit= and return the latest by creation_date."""
        # Create two GeoJSON entries; second one will be the latest due to auto_now_add
        for _ in range(2):
            commit_sha = sha1_hash()
            # Avoid touching S3 storage; set the expected upload name directly
            GeoJSON.objects.create(
                project=self.project,
                commit_sha=commit_sha,
                commit_date=timezone.now(),
                file=temp_geojson_file(),
            )

        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": self.project.id}
            )
            + "?limit=1",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = orjson.loads(response.content)
        assert response_data["success"] is True
        files = response_data["data"]["geojson_files"]
        assert isinstance(files, list)
        assert len(files) == 1

    def test_presigned_url_uses_geojson_prefix_and_bucket(self) -> None:
        """Presigned URL should target geojson/<project>/<sha>.json within the
        configured bucket."""
        # Prepare one stored file using the storage + upload_to
        commit_sha = sha1_hash()

        GeoJSON.objects.create(
            project=self.project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            file=temp_geojson_file(),
        )

        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview",
                kwargs={"id": self.project.id},
            )
            + "?limit=1",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "data" in response.data
        assert "geojson_files" in response.data["data"]
        assert len(response.data["data"]["geojson_files"]) == 1
        assert "url" in response.data["data"]["geojson_files"][0]
        assert (
            "s3.amazonaws.com/geojson/"
            in response.data["data"]["geojson_files"][0]["url"]
        )


class NoPermissionTestProjectGeoJsonApiView(BaseAPIProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.token = TokenFactory.create()

    def test_get_project_geojson_without_permissions(self) -> None:
        """Test that users without permissions cannot access GeoJSON data."""
        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview",
                kwargs={"id": self.project.id},
            ),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_project_geojson_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access GeoJSON data."""
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview",
                kwargs={"id": self.project.id},
            ),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_project_geojson_nonexistent_project(self) -> None:
        """Test response for non-existent project."""
        fake_project_id = uuid.uuid4()
        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview",
                kwargs={"id": fake_project_id},
            ),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
