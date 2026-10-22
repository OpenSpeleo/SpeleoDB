# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from parameterized.parameterized import parameterized_class
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import NoteStationResourceFactory
from speleodb.api.v2.tests.factories import SubSurfaceStationFactory
from speleodb.api.v2.tests.file_utils import sha256_from_url
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import StationResourceType
from speleodb.gis.models import Station
from speleodb.gis.models import StationResource
from speleodb.gis.models import SubSurfaceStation
from speleodb.utils.sanitize import sanitize_text
from speleodb.utils.test_utils import named_product

ARTIFACT_DIR = Path(__file__).parent / "artifacts"


class TestStationResourceAPI(BaseAPIProjectTestCase):
    """Test cases for Station Resource CRUD operations."""

    level = PermissionLevel.ADMIN
    permission_type = PermissionType.USER
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

        # Create a station for testing
        self.resource_url = reverse(
            "api:v2:station-resources",
            kwargs={"id": self.station.id},
        )

    def _create_test_image(self, name: str = "test.jpg") -> SimpleUploadedFile:
        """Create a test image file."""
        # Load real image from artifacts
        artifacts_dir = Path(__file__).parent / "artifacts"
        with (artifacts_dir / "image.jpg").open(mode="rb") as f:
            jpeg_content = f.read()
        return SimpleUploadedFile(name, jpeg_content, content_type="image/jpeg")

    def _create_test_text_file(
        self, name: str = "test.txt", content: str = "Test content"
    ) -> SimpleUploadedFile:
        """Create a test text file."""
        return SimpleUploadedFile(name, content.encode(), content_type="text/plain")

    def test_list_resources_empty(self) -> None:
        """Test listing resources when none exist."""
        response = self.client.get(
            self.resource_url,
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_list_resources_with_data(self) -> None:
        """Test listing resources when they exist."""
        # Create some resources
        StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="Test Note",
            text_content="Some notes",
            created_by=self.user.email,
            station=self.station,
        )
        StationResource.objects.create(
            resource_type=StationResourceType.PHOTO,
            title="Test Photo",
            file=self._create_test_image(),
            created_by=self.user.email,
            station=self.station,
        )

        response = self.client.get(
            self.resource_url,
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        resources = response.data
        assert len(resources) == 2  # noqa: PLR2004

        # Check ordering - should be ordered by most recent modified date first
        # Since resource2 was created after resource1, it should appear first
        assert resources[0]["title"] == "Test Photo"
        assert resources[1]["title"] == "Test Note"

    def test_create_photo_resource(self) -> None:
        """Test creating a photo resource."""
        image_file = self._create_test_image()
        data = {
            "resource_type": StationResourceType.PHOTO,
            "title": "Cave Entrance Photo",
            "description": "Main entrance view",
            "file": image_file,
        }

        response = self.client.post(
            self.resource_url,
            data,
            format="multipart",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        resource = response.data
        assert resource["title"] == "Cave Entrance Photo"
        assert resource["resource_type"] == StationResourceType.PHOTO
        assert resource["file"] is not None
        assert resource["created_by"] == self.user.email

    def test_create_video_resource(self) -> None:
        with (ARTIFACT_DIR / "video.mp4").open(mode="rb") as f:
            video_file = SimpleUploadedFile(
                "video.mp4", f.read(), content_type="video/mp4"
            )

        data = {
            "resource_type": StationResourceType.VIDEO,
            "title": "Cave Tour Video",
            "description": "Walkthrough video",
            "file": video_file,
        }

        response = self.client.post(
            self.resource_url,
            data,
            format="multipart",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        resource = response.data
        assert resource["resource_type"] == StationResourceType.VIDEO

    def test_create_note_resource(self) -> None:
        """Test creating a note resource."""
        data = {
            "resource_type": StationResourceType.NOTE,
            "title": "Field Notes",
            "description": "Important observations",
            "text_content": "The cave entrance is partially blocked by debris...",
        }

        response = self.client.post(
            self.resource_url,
            data,
            format="json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        resource = response.data
        assert resource["resource_type"] == StationResourceType.NOTE
        assert resource["text_content"] == data["text_content"]
        assert resource["file"] is None

    def test_create_document_resource(self) -> None:
        """Test creating a document resource."""
        doc_file = self._create_test_text_file("report.txt", "Cave survey report...")
        data = {
            "resource_type": StationResourceType.DOCUMENT,
            "title": "Survey Report",
            "description": "Detailed findings",
            "file": doc_file,
        }

        response = self.client.post(
            self.resource_url,
            data,
            format="multipart",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        resource = response.data
        assert resource["resource_type"] == StationResourceType.DOCUMENT

    def test_create_resource_missing_file(self) -> None:
        """Test creating a file-based resource without a file."""
        data = {
            "resource_type": StationResourceType.PHOTO,
            "title": "Missing Photo",
            "description": "This should fail",
        }

        response = self.client.post(
            self.resource_url,
            data,
            format="json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "requires a file" in str(response.data["errors"])

    def test_create_resource_missing_text(self) -> None:
        """Test creating a text-based resource without text content."""
        data = {
            "resource_type": StationResourceType.NOTE,
            "title": "Empty Note",
            "description": "This should fail",
        }

        response = self.client.post(
            self.resource_url,
            data,
            format="json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "requires text content" in str(response.data["errors"])

    def test_retrieve_resource(self) -> None:
        """Test retrieving a single resource."""
        resource = StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="Test Note",
            text_content="Content",
            created_by=self.user.email,
            station=self.station,
        )

        url = reverse("api:v2:resource-detail", kwargs={"id": resource.id})
        response = self.client.get(url, headers={"authorization": self.auth})

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["id"] == str(resource.id)
        assert data["title"] == "Test Note"

    def test_update_resource(self) -> None:
        """Test updating a resource."""
        resource = StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="Old Title",
            text_content="Old content",
            created_by=self.user.email,
            station=self.station,
        )

        reverse("api:v2:resource-detail", kwargs={"id": resource.id})
        update_data = {
            "title": "New Title",
            "description": "Updated description",
            "text_content": "New content",
        }

        url = reverse("api:v2:resource-detail", kwargs={"id": resource.id})

        response = self.client.patch(
            url,
            update_data,
            format="json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        updated = response.data
        assert updated["title"] == "New Title"
        assert updated["description"] == "Updated description"
        assert updated["text_content"] == "New content"

    def test_update_resource_file(self) -> None:
        """Test updating a file resource with a new file."""
        # Create initial resource
        resource = StationResource.objects.create(
            resource_type=StationResourceType.PHOTO,
            title="Old Photo",
            file=self._create_test_image("old.jpg"),
            created_by=self.user.email,
            station=self.station,
        )
        original_filename = resource.file.name

        # Update with new file
        new_image = self._create_test_image("new.jpg")
        update_data = {
            "title": "New Photo",
            "file": new_image,
        }

        url = reverse("api:v2:resource-detail", kwargs={"id": resource.id})

        response = self.client.patch(
            url, update_data, format="multipart", headers={"authorization": self.auth}
        )

        assert response.status_code == status.HTTP_200_OK
        updated = response.data
        assert updated["title"] == "New Photo"
        resource.refresh_from_db()
        assert resource.file.name != original_filename

        sha256 = hashlib.sha256()
        for chunk in new_image.chunks():
            sha256.update(chunk)

        expected_digest = sha256.hexdigest()

        assert expected_digest == sha256_from_url(updated["file"])

    def test_delete_resource(self) -> None:
        """Test deleting a resource."""
        resource = StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="To Delete",
            text_content="Content",
            created_by=self.user.email,
            station=self.station,
        )

        url = reverse("api:v2:resource-detail", kwargs={"id": resource.id})
        response = self.client.delete(url, headers={"authorization": self.auth})

        assert response.status_code == status.HTTP_200_OK
        # Verify deletion
        assert not StationResource.objects.filter(id=resource.id).exists()

    def test_delete_resource_with_file(self) -> None:
        """Test deleting a resource also removes the file."""
        resource = StationResource.objects.create(
            resource_type=StationResourceType.PHOTO,
            title="Photo to Delete",
            file=self._create_test_image(),
            created_by=self.user.email,
            station=self.station,
        )
        resource_id = resource.id
        stored_files = [
            (field.storage, field.name)
            for field in (resource.file, resource.miniature)
            if field.name
        ]
        assert stored_files
        assert all(storage.exists(name) for storage, name in stored_files)

        url = reverse("api:v2:resource-detail", kwargs={"id": resource.id})
        response = self.client.delete(url, headers={"authorization": self.auth})

        assert response.status_code == status.HTTP_200_OK

        # Verify resource is deleted
        assert not StationResource.objects.filter(id=resource_id).exists()
        assert all(not storage.exists(name) for storage, name in stored_files)

    def test_resource_ordering(self) -> None:
        """Test resources are returned in correct order by modified date."""
        # Create resources with different modified times
        StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="Third",
            text_content="3",
            created_by=self.user.email,
            station=self.station,
        )
        StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="First",
            text_content="1",
            created_by=self.user.email,
            station=self.station,
        )
        StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="Second",
            text_content="2",
            created_by=self.user.email,
            station=self.station,
        )

        response = self.client.get(
            self.resource_url,
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK

        resources = response.data

        # Resources should be ordered by most recent modified date
        # Since r2 was created last, it should be first
        assert resources[0]["title"] == "Second"
        assert resources[1]["title"] == "First"
        assert resources[2]["title"] == "Third"


class TestUnauthenticatedStationResourceAPIAuthentication(BaseAPIProjectTestCase):
    """Test authentication requirements for station resource API endpoints."""

    level: PermissionLevel
    permission_type: PermissionType
    station: Station

    def setUp(self) -> None:
        super().setUp()
        self.station = SubSurfaceStationFactory.create(project=self.project)

    def test_resource_list_requires_authentication(self) -> None:
        """Test that resource list endpoint requires authentication."""
        response = self.client.get(
            reverse("api:v2:station-resources", kwargs={"id": uuid.uuid4()})
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_resource_create_requires_authentication(self) -> None:
        """Test that resource create endpoint requires authentication."""
        data = {
            "resource_type": StationResourceType.NOTE,
            "title": "Test Note",
            "text_content": "This is a test note",
        }
        response = self.client.post(
            reverse(
                "api:v2:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@parameterized_class(
    [
        "level",
        "permission_type",
    ],
    [
        (level, permission_type)
        for level, permission_type in named_product(
            level=[
                PermissionLevel.ADMIN,
                PermissionLevel.READ_AND_WRITE,
                PermissionLevel.READ_ONLY,
                PermissionLevel.WEB_VIEWER,
            ],
            permission_type=[PermissionType.USER, PermissionType.TEAM],
        )
        if (level, permission_type) != (PermissionLevel.ADMIN, PermissionType.TEAM)
    ],
)
class TestStationResourceAPIPermissions(BaseAPIProjectTestCase):
    """Test permission requirements for station resource API endpoints."""

    level: PermissionLevel
    permission_type: PermissionType
    station: Station

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=self.level, permission_type=self.permission_type
        )
        self.station = SubSurfaceStationFactory.create(project=self.project)

    def test_create_note_resource(self) -> None:
        """Test creating a note resource."""
        data = {
            "resource_type": StationResourceType.NOTE,
            "title": "Cave Survey Notes",
            "description": "Detailed observations from the survey",
            "text_content": (
                "The cave entrance is approximately 2m wide and 1.5m high. Temperature "
                "is constant at around 12°C."
            ),
        }

        response = self.client.post(
            reverse(
                "api:v2:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_201_CREATED

        resource_data = response.data
        assert resource_data["resource_type"] == StationResourceType.NOTE
        assert resource_data["title"] == "Cave Survey Notes"
        assert resource_data["text_content"] == data["text_content"]

    def test_list_station_resources(self) -> None:
        """Test listing resources for a station."""
        # Create multiple resources
        resources = [
            NoteStationResourceFactory.create(station=self.station),
            NoteStationResourceFactory.create(station=self.station),
        ]

        response = self.client.get(
            reverse(
                "api:v2:station-resources",
                kwargs={"id": self.station.id},
            )
            + f"?station_id={self.station.id}",
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == len(resources)

        # Verify all resources are present (without depending on order)
        response_resource_ids = {r["id"] for r in response.data}
        expected_resource_ids = {str(r.id) for r in resources}
        assert response_resource_ids == expected_resource_ids

    def test_get_resource_detail(self) -> None:
        """Test getting resource detail."""
        resource = NoteStationResourceFactory.create(
            station=self.station,
            title="Detailed Note",
            text_content="This is a detailed note about the cave survey.",
        )

        response = self.client.get(
            reverse(
                "api:v2:resource-detail",
                kwargs={"id": resource.id},
            ),
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK

        resource_data = response.data
        assert resource_data["id"] == str(resource.id)
        assert resource_data["title"] == "Detailed Note"
        assert resource_data["text_content"] == resource.text_content

    def test_update_resource(self) -> None:
        """Test updating a resource."""
        resource = NoteStationResourceFactory.create(station=self.station)

        data = {
            "title": "Updated Note Title",
            "description": "Updated description",
            "text_content": "Updated note content with more details.",
        }

        response = self.client.patch(
            reverse(
                "api:v2:resource-detail",
                kwargs={"id": resource.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK

        resource_data = response.data
        assert resource_data["title"] == "Updated Note Title"
        assert resource_data["description"] == "Updated description"
        assert (
            resource_data["text_content"] == "Updated note content with more details."
        )

    def test_delete_resource(self) -> None:
        """Test deleting a resource."""
        resource = NoteStationResourceFactory.create(station=self.station)
        resource_id = resource.id

        response = self.client.delete(
            reverse(
                "api:v2:resource-detail",
                kwargs={"id": resource.id},
            ),
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.ADMIN:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert "id" in response.data
        assert response.data["id"] == str(resource_id)

        # Verify resource was deleted
        assert not StationResource.objects.filter(id=resource_id).exists()


class TestStationResourceValidation(BaseAPIProjectTestCase):
    """Test validation for station resource data."""

    level = PermissionLevel.ADMIN
    permission_type = PermissionType.USER
    station: Station

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=self.level, permission_type=self.permission_type
        )
        self.station = SubSurfaceStationFactory.create(project=self.project)

    def test_create_resource_missing_title(self) -> None:
        """Test creating a resource without a title."""
        data = {
            "resource_type": StationResourceType.NOTE,
            "text_content": "Note without title",
        }

        response = self.client.post(
            reverse(
                "api:v2:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "title" in response.data["errors"]

    def test_create_resource_invalid_type(self) -> None:
        """Test creating a resource with invalid type."""
        data = {
            "resource_type": "invalid_type",
            "title": "Invalid Resource",
            "text_content": "This has an invalid type",
        }

        response = self.client.post(
            reverse(
                "api:v2:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "resource_type" in response.data["errors"]

    def test_create_resource_title_too_long(self) -> None:
        """Test creating a resource with title too long."""
        long_title = "A" * 201  # Exceeds max length of 200
        data = {
            "resource_type": StationResourceType.NOTE,
            "title": long_title,
            "text_content": "Note with very long title",
        }

        response = self.client.post(
            reverse(
                "api:v2:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestStationResourceFileHandling(BaseAPIProjectTestCase):
    """Test file handling for station resources."""

    level = PermissionLevel.ADMIN
    permission_type = PermissionType.USER
    station: Station

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=self.level, permission_type=self.permission_type
        )
        self.station = SubSurfaceStationFactory.create(project=self.project)

    def test_file_upload_with_checksum_verification(self) -> None:
        """Test file upload with SHA256 checksum verification."""
        # Create a test file with known content
        test_content = b"This is a test file for checksum verification. It contains specific data that will produce a predictable SHA256 hash."  # noqa: E501
        expected_sha256 = hashlib.sha256(test_content).hexdigest()

        uploaded_file = SimpleUploadedFile(
            "test_checksum.txt", test_content, content_type="text/plain"
        )

        data = {
            "resource_type": StationResourceType.DOCUMENT,
            "title": "Checksum Test Document",
            "description": "Document for testing file integrity",
            "file": uploaded_file,
        }

        response = self.client.post(
            reverse(
                "api:v2:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED

        # Retrieve the created resource
        resource = StationResource.objects.get(id=response.data["id"])

        # Read the stored file and verify checksum
        assert resource.file
        with resource.file.open("rb") as f:
            stored_content = f.read()

        actual_sha256 = hashlib.sha256(stored_content).hexdigest()
        assert actual_sha256 == expected_sha256, "File integrity check failed"

    def test_invalid_file_extension(self) -> None:
        """Test uploading file with invalid extension."""
        # Try uploading a file with disallowed extension
        uploaded_file = SimpleUploadedFile(
            "test.exe",  # Executable file not allowed
            b"fake_executable_content",
            content_type="application/x-executable",
        )

        data = {
            "resource_type": StationResourceType.DOCUMENT,
            "title": "Invalid File Type",
            "description": "Testing invalid file extension",
            "file": uploaded_file,
        }

        response = self.client.post(
            reverse(
                "api:v2:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_empty_file_upload(self) -> None:
        """Test uploading an empty file."""
        uploaded_file = SimpleUploadedFile(
            "empty.txt",
            b"",  # Empty content
            content_type="text/plain",
        )

        data = {
            "resource_type": StationResourceType.DOCUMENT,
            "title": "Empty File",
            "description": "Testing empty file upload",
            "file": uploaded_file,
        }

        response = self.client.post(
            reverse(
                "api:v2:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestStationResourceFuzzing(BaseAPIProjectTestCase):
    """Fuzzy testing for station resource API endpoints."""

    level = PermissionLevel.ADMIN
    permission_type = PermissionType.USER
    station: Station

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=self.level, permission_type=self.permission_type
        )
        self.station = SubSurfaceStationFactory.create(project=self.project)

    def test_fuzz_resource_data(self) -> None:
        """Test resource creation with various data types."""

        # Test with various data combinations
        fuzz_data_sets = [
            # Edge case titles
            {
                "resource_type": StationResourceType.NOTE,
                "title": "A" * 200,  # Max length
                "text_content": "Test",
            },
            # XSS payloads (nh3 strips script tags AND their content)
            {
                "resource_type": StationResourceType.NOTE,
                "title": "Special Characters: !@#$%^&*()",
                "text_content": "Safe text <b onmouseover=alert(1)>with XSS</b>",
            },
            # Unicode content
            {
                "resource_type": StationResourceType.NOTE,
                "title": "Unicode Test: 中文测试 🎉",
                "text_content": "Unicode content: αβγδε",
            },
        ]

        for idx, data in enumerate(fuzz_data_sets):
            data.update({"station_id": str(self.station.id)})
            response = self.client.post(
                reverse(
                    "api:v2:station-resources",
                    kwargs={"id": self.station.id},
                ),
                data=data,
                headers={"authorization": self.auth},
            )

            assert response.status_code == status.HTTP_201_CREATED, idx
            assert response.data["title"] == sanitize_text(data["title"])
            assert response.data["text_content"] == sanitize_text(data["text_content"])

    def test_fuzz_file_uploads_errors(self) -> None:
        """Test file uploads with various file types and content."""

        # Test various file scenarios
        file_tests = [
            # Invalid file extension
            (
                StationResourceType.PHOTO,
                "test.jpoog",
                (ARTIFACT_DIR / "image.jpg").read_bytes(),
                "image/jpeg",
                status.HTTP_400_BAD_REQUEST,
            ),
            # Invalid file extension
            (
                StationResourceType.PHOTO,
                "test.jpg",
                b"image",
                "image/jpeg",
                status.HTTP_400_BAD_REQUEST,
            ),
            # Filename too long
            (
                StationResourceType.DOCUMENT,
                "a" * 200 + ".pdf",
                (ARTIFACT_DIR / "document.pdf").read_bytes(),
                "application/pdf",
                status.HTTP_400_BAD_REQUEST,
            ),
            # Special characters in filename
            (
                StationResourceType.DOCUMENT,
                "test file with spaces & symbols!.pdf",
                (ARTIFACT_DIR / "document.pdf").read_bytes(),
                "application/pdf",
                status.HTTP_201_CREATED,
            ),
            # Unicode filename
            (
                StationResourceType.DOCUMENT,
                "测试文件.pdf",
                (ARTIFACT_DIR / "document.pdf").read_bytes(),
                "application/pdf",
                status.HTTP_201_CREATED,
            ),
        ]

        for idx, (
            resource_type,
            filename,
            content,
            content_type,
            expected_status,
        ) in enumerate(file_tests):
            uploaded_file = SimpleUploadedFile(filename, content, content_type)

            data = {
                "resource_type": resource_type,
                "title": f"Fuzz Test: {filename}",
                "file": uploaded_file,
            }

            response = self.client.post(
                reverse(
                    "api:v2:station-resources",
                    kwargs={"id": self.station.id},
                ),
                data=data,
                headers={"authorization": self.auth},
            )

            assert response.status_code == expected_status, idx
