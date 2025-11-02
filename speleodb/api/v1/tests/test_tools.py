# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.tests.base_testcase import BaseAPITestCase


@pytest.mark.django_db
class TestXLS2MnemoDMP(BaseAPITestCase):
    def setUp(self) -> None:
        super().setUp()

        self.url = reverse("api:v1:tool-xls2dmp")

    def test_requires_authentication(self) -> None:
        client = APIClient()
        response = client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_xls_to_compass_dat(self) -> None:
        data = {
            "shots": [
                {
                    "length": "62.45",
                    "azimuth": "104",
                    "depth": "25",
                    "left": "12",
                    "right": "13",
                    "up": "14",
                    "down": "15",
                },
                {
                    "length": "23",
                    "azimuth": "89.23",
                    "depth": "35",
                    "left": "",
                    "right": "",
                    "up": "",
                    "down": "",
                },
                {
                    "length": "105.32",
                    "azimuth": "140.11",
                    "depth": "32",
                    "left": "",
                    "right": "",
                    "up": "",
                    "down": "",
                },
                {
                    "length": "20",
                    "azimuth": "280",
                    "depth": "35",
                    "left": "",
                    "right": "",
                    "up": "",
                    "down": "",
                },
                {
                    "length": "32.34",
                    "azimuth": "359.88",
                    "depth": "67",
                    "left": "60",
                    "right": "70",
                    "up": "80",
                    "down": "90",
                },
                {
                    "length": "87.23",
                    "azimuth": "1.06",
                    "depth": "73.44",
                    "left": "",
                    "right": "",
                    "up": "",
                    "down": "",
                },
            ],
            "survey_date": "2025-10-27",
            "unit": "feet",
            "direction": "in",
        }

        # Limit should be 10
        response = self.client.post(
            self.url,
            data=data,
            headers={"authorization": self.auth},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

        assert hasattr(response, "streaming_content")

        content = "".join(
            chunk if isinstance(chunk, str) else chunk.decode("utf-8")
            for chunk in response.streaming_content  # pyright: ignore[reportAttributeAccessIssue]
        )

        assert (
            hashlib.sha256(content.encode("utf-8")).hexdigest()
            == "7850f283314dacd212ffc756e128876aa40c65f29abcd21593111d7a84251640"
        ), content


@pytest.mark.django_db
class TestXLS2Compass(BaseAPITestCase):
    def setUp(self) -> None:
        super().setUp()

        self.url = reverse("api:v1:tool-xls2compass")

    def test_requires_authentication(self) -> None:
        client = APIClient()
        response = client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_xls_to_compass_dat(self) -> None:
        data = {
            "shots": [
                {
                    "station": "A1",
                    "depth": "12.00",
                    "length": "62.45",
                    "azimuth": "104.00",
                    "left": "",
                    "right": "",
                    "up": "",
                    "down": "",
                    "flags": "#|P#",
                    "comment": "",
                },
                {
                    "station": "SS1",
                    "depth": "25.00",
                    "length": "23.00",
                    "azimuth": "89.23",
                    "left": "",
                    "right": "",
                    "up": "",
                    "down": "",
                    "flags": "#|PLCXSS#",
                    "comment": "Nice jump promising on the right",
                },
                {
                    "station": "SS2",
                    "depth": "35.00",
                    "length": "105.32",
                    "azimuth": "140.11",
                    "left": "",
                    "right": "",
                    "up": "",
                    "down": "",
                    "flags": "PLCXSS",
                    "comment": "Lead to the SW of the main tunnel - going down",
                },
                {
                    "station": "SS3",
                    "depth": "32.00",
                    "length": "20.00",
                    "azimuth": "280.00",
                    "left": "",
                    "right": "",
                    "up": "",
                    "down": "",
                    "flags": "",
                    "comment": "",
                },
                {
                    "station": "SS4",
                    "depth": "35.00",
                    "length": "32.34",
                    "azimuth": "359.88",
                    "left": "",
                    "right": "",
                    "up": "",
                    "down": "",
                    "flags": "",
                    "comment": "",
                },
                {
                    "station": "SS5",
                    "depth": "67.00",
                    "length": "87.23",
                    "azimuth": "1.06",
                    "left": "",
                    "right": "",
                    "up": "",
                    "down": "",
                    "flags": "",
                    "comment": "",
                },
                {
                    "station": "SS6",
                    "depth": "73.44",
                    "length": "",
                    "azimuth": "",
                    "left": "",
                    "right": "",
                    "up": "",
                    "down": "",
                    "flags": "",
                    "comment": "",
                },
            ],
            "survey_date": "2025-10-29",
            "unit": "feet",
            "cave_name": "Cool Cave",
            "survey_name": "Cool Survey",
            "survey_team": [],
            "comment": "",
            "latitude": 29.6519684,
            "longitude": -82.3249846,
        }

        # Limit should be 10
        response = self.client.post(
            self.url,
            data=data,
            headers={"authorization": self.auth},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

        assert hasattr(response, "streaming_content")

        content = "".join(
            chunk if isinstance(chunk, str) else chunk.decode("utf-8")
            for chunk in response.streaming_content  # pyright: ignore[reportAttributeAccessIssue]
        )

        assert (
            hashlib.sha256(content.encode("utf-8")).hexdigest()
            == "5fac2d5a43f007e32cd6c04a4581e20086e59e8bf0c4126a0c5696f34626cb8f"
        ), content
