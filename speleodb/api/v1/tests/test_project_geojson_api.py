# -*- coding: utf-8 -*-

from __future__ import annotations

import random
import string
import tempfile
import uuid
from hashlib import sha1
from typing import Any

import orjson
from django.urls import reverse
from unittest.mock import patch
from parameterized.parameterized import parameterized_class
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.surveys.models import GeoJSON
from speleodb.surveys.models import PermissionLevel
from speleodb.utils.test_utils import named_product


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

        # Set up some test GeoJSON data
        self.test_geojson = {
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

    def test_geojson_endpoint_performance_uses_with_geojson_manager(self) -> None:
        """Test that the endpoint properly loads geojson field."""
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".geojson", delete=False
        ) as temp_file:
            temp_file.write(orjson.dumps(self.test_geojson))

            # Set some test GeoJSON data
            GeoJSON.objects.create(
                project=self.project,
                commit_sha=sha1_hash(),
                file=temp_file.name,
            )

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": self.project.id}
            ),
            headers={"authorization": auth},
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
            sha = sha1_hash()
            # Avoid touching S3 storage; set the expected upload name directly
            GeoJSON.objects.create(
                project=self.project,
                commit_sha=sha,
                file=f"{self.project.id}/{sha}.json",
            )

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": self.project.id}
            )
            + "?limit=1",
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = orjson.loads(response.content)
        assert response_data["success"] is True
        files = response_data["data"]["geojson_files"]
        assert isinstance(files, list)
        assert len(files) == 1

    def test_presigned_url_uses_geojson_prefix_and_bucket(self) -> None:
        """Presigned URL should target geojson/<project>/<sha>.json within the configured bucket."""
        # Prepare one stored file using the storage + upload_to
        sha = sha1_hash()
        # Avoid touching S3 storage; set the expected upload name directly
        GeoJSON.objects.create(
            project=self.project, commit_sha=sha, file=f"{self.project.id}/{sha}.json"
        )

        captured_params: list[dict[str, str]] = []

        class _FakeS3Client:
            def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):  # type: ignore[no-untyped-def]
                captured_params.append(Params)
                return "https://example.test/signed"

        with patch("speleodb.surveys.models.geojson.boto3.client", return_value=_FakeS3Client()):
            auth = self.header_prefix + self.token.key
            response = self.client.get(
                reverse(
                    "api:v1:one_project_geojson_apiview",
                    kwargs={"id": self.project.id},
                )
                + "?limit=1",
                headers={"authorization": auth},
            )

        assert response.status_code == status.HTTP_200_OK
        assert len(captured_params) == 1
        params = captured_params[0]
        assert "Bucket" in params and isinstance(params["Bucket"], str)
        # Expect the key to include the geojson/ prefix and project id + sha
        expected_prefix = "geojson/" + str(self.project.id) + "/"
        assert params["Key"].startswith(expected_prefix)
        assert params["Key"].endswith(sha + ".json")


class NoPermissionTestProjectGeoJsonApiView(BaseAPIProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.token = TokenFactory.create()

    def test_get_project_geojson_without_permissions(self) -> None:
        """Test that users without permissions cannot access GeoJSON data."""
        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": self.project.id}
            ),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_project_geojson_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access GeoJSON data."""
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": self.project.id}
            ),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_project_geojson_nonexistent_project(self) -> None:
        """Test response for non-existent project."""
        fake_project_id = uuid.uuid4()
        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": fake_project_id}
            ),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
