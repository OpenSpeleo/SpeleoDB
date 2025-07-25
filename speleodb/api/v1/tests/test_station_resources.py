# -*- coding: utf-8 -*-
"""Tests for Station Resource API endpoints."""

from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Station
from speleodb.surveys.models import StationResource


class TestStationResourceAPI(BaseAPIProjectTestCase):
    """Test cases for Station Resource CRUD operations."""

    def setUp(self) -> None:
        """Set up test data."""
        super().setUp()
        # Set up authentication
        self.auth = f"{self.header_prefix}{self.token.key}"

        # Give user permission to the project
        self.set_test_project_permission(PermissionLevel.READ_AND_WRITE)

        # Create a station for testing
        self.station = Station.objects.create(
            project=self.project,
            name="Test Station",
            latitude=45.1234567,
            longitude=-122.7654321,
            created_by=self.user,
        )
        self.resource_url = "/api/v1/resources/"

    def _create_test_image(
        self, name: str = "test.jpg", size: tuple[int, int] = (100, 100)
    ) -> SimpleUploadedFile:
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
            f"{self.resource_url}?station_id={self.station.id}",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]
        assert response.data["data"]["resources"] == []

    def test_list_resources_with_data(self) -> None:
        """Test listing resources when they exist."""
        # Create some resources
        StationResource.objects.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="Test Note",
            text_content="Some notes",
            created_by=self.user,
            station=self.station,
        )
        StationResource.objects.create(
            resource_type=StationResource.ResourceType.PHOTO,
            title="Test Photo",
            file=self._create_test_image(),
            created_by=self.user,
            station=self.station,
        )

        response = self.client.get(
            f"{self.resource_url}?station_id={self.station.id}",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]
        resources = response.data["data"]["resources"]
        assert len(resources) == 2  # noqa: PLR2004

        # Check ordering - should be ordered by most recent modified date first
        # Since resource2 was created after resource1, it should appear first
        assert resources[0]["title"] == "Test Photo"
        assert resources[1]["title"] == "Test Note"

    def test_create_photo_resource(self) -> None:
        """Test creating a photo resource."""
        image_file = self._create_test_image()
        data = {
            "station_id": str(self.station.id),
            "resource_type": StationResource.ResourceType.PHOTO,
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
        assert response.data["success"]

        resource = response.data["data"]["resource"]
        assert resource["title"] == "Cave Entrance Photo"
        assert resource["resource_type"] == StationResource.ResourceType.PHOTO
        assert resource["file_url"] is not None
        assert resource["created_by_email"] == self.user.email

    def test_create_video_resource(self) -> None:
        """Test creating a video resource."""
        # Create a minimal valid MP4 file
        video_content = (
            b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00"  # Minimal MP4 header
        )
        video_file = SimpleUploadedFile(
            "test.mp4", video_content, content_type="video/mp4"
        )

        data = {
            "station_id": str(self.station.id),
            "resource_type": StationResource.ResourceType.VIDEO,
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
        assert response.data["success"]

        resource = response.data["data"]["resource"]
        assert resource["resource_type"] == StationResource.ResourceType.VIDEO

    def test_create_note_resource(self) -> None:
        """Test creating a note resource."""
        data = {
            "station_id": str(self.station.id),
            "resource_type": StationResource.ResourceType.NOTE,
            "title": "Field Notes",
            "description": "Important observations",
            "text_content": "The cave entrance is partially blocked by debris...",
        }

        response = self.client.post(
            self.resource_url, data, format="json", headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["success"]

        resource = response.data["data"]["resource"]
        assert resource["resource_type"] == StationResource.ResourceType.NOTE
        assert resource["text_content"] == data["text_content"]
        assert resource["file_url"] is None

    def test_create_sketch_resource(self) -> None:
        """Test creating a sketch resource."""
        svg_content = '<svg><circle cx="50" cy="50" r="40" /></svg>'
        data = {
            "station_id": str(self.station.id),
            "resource_type": StationResource.ResourceType.SKETCH,
            "title": "Cave Map Sketch",
            "description": "Rough layout",
            "text_content": svg_content,
        }

        response = self.client.post(
            self.resource_url, data, format="json", headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["success"]

        resource = response.data["data"]["resource"]
        assert resource["resource_type"] == StationResource.ResourceType.SKETCH
        assert resource["text_content"] == svg_content

    def test_create_document_resource(self) -> None:
        """Test creating a document resource."""
        doc_file = self._create_test_text_file("report.txt", "Cave survey report...")
        data = {
            "station_id": str(self.station.id),
            "resource_type": StationResource.ResourceType.DOCUMENT,
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
        assert response.data["success"]

        resource = response.data["data"]["resource"]
        assert resource["resource_type"] == StationResource.ResourceType.DOCUMENT

    def test_create_resource_missing_file(self) -> None:
        """Test creating a file-based resource without a file."""
        data = {
            "station_id": str(self.station.id),
            "resource_type": StationResource.ResourceType.PHOTO,
            "title": "Missing Photo",
            "description": "This should fail",
        }

        response = self.client.post(
            self.resource_url, data, format="json", headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not response.data["success"]
        assert "requires a file" in str(response.data["errors"])

    def test_create_resource_missing_text(self) -> None:
        """Test creating a text-based resource without text content."""
        data = {
            "station_id": str(self.station.id),
            "resource_type": StationResource.ResourceType.NOTE,
            "title": "Empty Note",
            "description": "This should fail",
        }

        response = self.client.post(
            self.resource_url, data, format="json", headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not response.data["success"]
        assert "requires text content" in str(response.data["errors"])

    def test_retrieve_resource(self) -> None:
        """Test retrieving a single resource."""
        resource = StationResource.objects.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="Test Note",
            text_content="Content",
            created_by=self.user,
            station=self.station,
        )

        url = f"/api/v1/resources/{resource.id}/"
        response = self.client.get(url, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]

        data = response.data["data"]["resource"]
        assert data["id"] == str(resource.id)
        assert data["title"] == "Test Note"

    def test_update_resource(self) -> None:
        """Test updating a resource."""
        resource = StationResource.objects.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="Old Title",
            text_content="Old content",
            created_by=self.user,
            station=self.station,
        )

        url = f"/api/v1/resources/{resource.id}/"
        update_data = {
            "title": "New Title",
            "description": "Updated description",
            "text_content": "New content",
        }

        response = self.client.patch(
            url, update_data, format="json", headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]

        updated = response.data["data"]["resource"]
        assert updated["title"] == "New Title"
        assert updated["description"] == "Updated description"
        assert updated["text_content"] == "New content"

    def test_update_resource_file(self) -> None:
        """Test updating a file resource with a new file."""
        # Create initial resource
        resource = StationResource.objects.create(
            resource_type=StationResource.ResourceType.PHOTO,
            title="Old Photo",
            file=self._create_test_image("old.jpg"),
            created_by=self.user,
            station=self.station,
        )

        # Update with new file
        new_image = self._create_test_image("new.jpg", size=(200, 200))
        url = f"/api/v1/resources/{resource.id}/"
        update_data = {
            "title": "New Photo",
            "file": new_image,
        }

        response = self.client.patch(
            url, update_data, format="multipart", headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]

        updated = response.data["data"]["resource"]
        assert updated["title"] == "New Photo"
        assert "new.jpg" in updated["file_url"]

    def test_delete_resource(self) -> None:
        """Test deleting a resource."""
        resource = StationResource.objects.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="To Delete",
            text_content="Content",
            created_by=self.user,
            station=self.station,
        )

        url = f"/api/v1/resources/{resource.id}/"
        response = self.client.delete(url, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]

        # Verify deletion
        assert not StationResource.objects.filter(id=resource.id).exists()

    def test_delete_resource_with_file(self) -> None:
        """Test deleting a resource also removes the file."""
        resource = StationResource.objects.create(
            resource_type=StationResource.ResourceType.PHOTO,
            title="Photo to Delete",
            file=self._create_test_image(),
            created_by=self.user,
            station=self.station,
        )
        resource_id = resource.id

        url = f"/api/v1/resources/{resource.id}/"
        response = self.client.delete(url, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK

        # Verify resource is deleted
        assert not StationResource.objects.filter(id=resource_id).exists()

    def test_resource_permissions_read_only(self) -> None:
        """Test read-only user cannot modify resources."""
        # Set user to read-only
        self.set_test_project_permission(PermissionLevel.READ_ONLY)

        # Can list resources
        response = self.client.get(
            f"{self.resource_url}?station_id={self.station.id}",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK

        # Cannot create
        data = {
            "station_id": str(self.station.id),
            "resource_type": StationResource.ResourceType.NOTE,
            "title": "Forbidden Note",
            "text_content": "Should not work",
        }
        response = self.client.post(
            self.resource_url, data, format="json", headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Create resource as admin for further tests
        resource = StationResource.objects.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="Test",
            text_content="Content",
            created_by=self.user,
            station=self.station,
        )
        url = f"/api/v1/resources/{resource.id}/"

        # Can retrieve
        response = self.client.get(url, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK

        # Cannot update
        response = self.client.patch(
            url, {"title": "New"}, format="json", headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Cannot delete
        response = self.client.delete(url, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_resource_ordering(self) -> None:
        """Test resources are returned in correct order by modified date."""
        # Create resources with different modified times
        StationResource.objects.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="Third",
            text_content="3",
            created_by=self.user,
            station=self.station,
        )
        StationResource.objects.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="First",
            text_content="1",
            created_by=self.user,
            station=self.station,
        )
        StationResource.objects.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="Second",
            text_content="2",
            created_by=self.user,
            station=self.station,
        )

        response = self.client.get(
            f"{self.resource_url}?station_id={self.station.id}",
            headers={"authorization": self.auth},
        )
        resources = response.data["data"]["resources"]

        # Resources should be ordered by most recent modified date
        # Since r2 was created last, it should be first
        assert resources[0]["title"] == "Second"
        assert resources[1]["title"] == "First"
        assert resources[2]["title"] == "Third"
