# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from parameterized.parameterized import parameterized
from parameterized.parameterized import parameterized_class
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.file_utils import create_test_image
from speleodb.api.v1.tests.file_utils import create_test_text_file
from speleodb.api.v1.tests.file_utils import create_test_video
from speleodb.api.v1.tests.file_utils import sha256_from_url
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Station
from speleodb.gis.models import StationLogEntry
from speleodb.gis.models import SubSurfaceStation
from speleodb.utils.test_utils import named_product


class TestStationLogEntryCreateAPIValidation(BaseAPIProjectTestCase):
    """Test file type validation for station resources."""

    def setUp(self) -> None:
        """Set up test data."""
        super().setUp()
        self.set_test_project_permission(
            PermissionLevel.READ_AND_WRITE, PermissionType.USER
        )
        self.station = SubSurfaceStation.objects.create(
            project=self.project,
            name="Test Station",
            latitude=45.0,
            longitude=-73.0,
            created_by=self.user.email,
        )

    def test_api_returns_validation_errors(self) -> None:
        """Test that API returns proper validation errors."""
        # Try to create with an invalid file extension.
        response = self.client.post(
            reverse("api:v1:station-logs", kwargs={"id": self.station.id}),
            {
                "title": "Test Illegal File",
                "attachment": create_test_text_file("test.xyz"),
            },
            format="multipart",
            headers={"authorization": self.header_prefix + self.token.key},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "errors" in data
        assert "attachment" in data["errors"]
        assert "File extension “xyz” is not allowed. Allowed extensions are: " in str(
            data["errors"]["attachment"][0]
        )

    @parameterized.expand(
        named_product(notes=["blablabla", None], attachment=[True, False])
    )
    def test_real_file_uploads(self, notes: str | None, attachment: bool) -> None:
        """Test with real artifact files."""
        artifacts_dir = Path(__file__).parent / "artifacts"

        data: dict[str, Any] = {"title": "Test Photo"}

        if notes:
            data["notes"] = notes

        if attachment:
            # Test valid photo upload
            with (artifacts_dir / "image.jpg").open(mode="rb") as f:
                data["attachment"] = SimpleUploadedFile(
                    "photo.jpg", f.read(), content_type="image/jpeg"
                )

        response = self.client.post(
            reverse("api:v1:station-logs", kwargs={"id": self.station.id}),
            data=data,
            format="multipart",
            headers={"authorization": self.header_prefix + self.token.key},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["title"] == data["title"]

        if attachment:
            assert "http" in response.data["data"]["attachment"]
        else:
            assert response.data["data"]["attachment"] is None

        if notes:
            assert response.data["data"]["notes"] == data["notes"]
        else:
            assert response.data["data"]["notes"] == ""


class BaseTestStationLogEntryGetAPI(BaseAPIProjectTestCase):
    """Test cases for Station Resource CRUD operations."""

    level: PermissionLevel
    permission_type: PermissionType
    station: Station

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=self.level, permission_type=self.permission_type
        )
        self.station = SubSurfaceStation.objects.create(
            project=self.project,
            name="Test Station",
            latitude=45.1234567,
            longitude=-122.7654321,
            created_by=self.user.email,
        )


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
class TestStationLogEntryListAPI(BaseTestStationLogEntryGetAPI):
    def setUp(self) -> None:
        super().setUp()

        # Create a station for testing
        self.station_logs_url = reverse(
            "api:v1:station-logs",
            kwargs={"id": self.station.id},
        )

    def test_list_logs_empty(self) -> None:
        """Test listing resources when none exist."""
        response = self.client.get(
            self.station_logs_url,
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]
        assert response.data["data"] == []

    def test_list_resources_with_data(self) -> None:
        """Test listing resources when they exist."""
        # Create some resources
        logs = [
            StationLogEntry.objects.create(
                title=f"Test Note {idx}",
                notes=f"Some notes {idx}",
                created_by=self.user.email,
                station=self.station,
                attachment=_attchmt,
            )
            for idx, _attchmt in enumerate(
                [
                    create_test_text_file(),
                    create_test_video(),
                    create_test_image(),
                    None,
                ]
            )
        ]

        response = self.client.get(
            self.station_logs_url,
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]

        # We have to reverse because the API returns from the most recently modified
        # Reversing provide the same order as in `logs`
        logs_data = list(reversed(response.data["data"]))
        assert len(logs_data) == len(logs)

        # Check ordering - should be ordered by most recent modified date first
        for idx in range(len(logs_data)):
            assert logs_data[idx]["title"] == f"Test Note {idx}"
            assert logs_data[idx]["notes"] == f"Some notes {idx}"
            assert logs_data[idx]["created_by"] == self.user.email
            assert logs_data[idx]["station"] == self.station.id

            if logs[idx].attachment:
                assert "http" in logs_data[idx]["attachment"]

                sha256 = hashlib.sha256()
                for chunk in logs[idx].attachment.chunks():
                    sha256.update(chunk)

                expected_digest = sha256.hexdigest()
                assert expected_digest == sha256_from_url(logs_data[idx]["attachment"])

            else:
                assert logs_data[idx]["attachment"] is None


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
class TestStationLogEntryDetailAPI(BaseTestStationLogEntryGetAPI):
    def setUp(self) -> None:
        super().setUp()

        self.log_entry = StationLogEntry.objects.create(
            title="Test Note",
            notes="Some notes",
            created_by=self.user.email,
            station=self.station,
            attachment=create_test_image(),
        )

    def _get_log_detail_url(self, log_entry: StationLogEntry) -> str:
        return reverse(
            "api:v1:log-detail",
            kwargs={"id": log_entry.id},
        )

    def test_retrieve_log_entry(self) -> None:
        """Test retrieving a single StationLogEntry."""

        response = self.client.get(
            self._get_log_detail_url(self.log_entry),
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]

        data = response.data["data"]
        assert data["id"] == str(self.log_entry.id)
        assert data["title"] == "Test Note"

    def test_update_logentry(self) -> None:
        """Test update a single StationLogEntry."""

        update_data = {
            "title": "New Title",
            "notes": "Updated notes",
            "text_content": "New content",
        }

        response = self.client.patch(
            self._get_log_detail_url(self.log_entry),
            update_data,
            format="json",
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]

        data = response.data["data"]
        assert data["id"] == str(self.log_entry.id)
        assert data["title"] == "New Title"
        assert data["notes"] == "Updated notes"

    def test_update_logentry_file(self) -> None:
        """Test updating a single StationLogEntry's attachment with a new file."""

        # Update with new file
        update_data = {
            "title": "New Video",
            "attachment": create_test_video(),
        }

        response = self.client.patch(
            self._get_log_detail_url(self.log_entry),
            update_data,
            format="multipart",
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]

        data = response.data["data"]
        assert data["id"] == str(self.log_entry.id)
        assert data["title"] == "New Video"

        sha256 = hashlib.sha256()
        for chunk in update_data["attachment"].chunks():  # type: ignore[attr-defined]
            sha256.update(chunk)

        expected_digest = sha256.hexdigest()
        assert expected_digest == sha256_from_url(data["attachment"])

    def test_delete_resource(self) -> None:
        """Test deleting a StationLogEntry."""

        response = self.client.delete(
            self._get_log_detail_url(self.log_entry),
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.ADMIN:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]

        # Verify deletion
        assert not StationLogEntry.objects.filter(id=self.log_entry.id).exists()
