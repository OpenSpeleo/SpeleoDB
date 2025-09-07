# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from faker import Faker
from parameterized.parameterized import parameterized
from parameterized.parameterized import parameterized_class
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.factories import NoteStationResourceFactory
from speleodb.api.v1.tests.factories import PhotoStationResourceFactory
from speleodb.api.v1.tests.factories import SketchStationResourceFactory
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Station
from speleodb.surveys.models import StationResource
from speleodb.surveys.models.station import StationResourceType
from speleodb.utils.test_utils import named_product


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
class TestStationResourceAPI(BaseAPIProjectTestCase):
    """Test cases for Station Resource CRUD operations."""

    level: PermissionLevel
    permission_type: PermissionType
    station: Station

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=self.level, permission_type=self.permission_type
        )
        self.station = Station.objects.create(
            project=self.project,
            name="Test Station",
            latitude=45.1234567,
            longitude=-122.7654321,
            created_by=self.user,
        )

        # Create a station for testing
        self.resource_url = reverse(
            "api:v1:station-resources",
            kwargs={"id": self.station.id},
        )

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
            self.resource_url,
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
        StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="Test Note",
            text_content="Some notes",
            created_by=self.user,
            station=self.station,
        )
        StationResource.objects.create(
            resource_type=StationResourceType.PHOTO,
            title="Test Photo",
            file=self._create_test_image(),
            created_by=self.user,
            station=self.station,
        )

        response = self.client.get(
            self.resource_url,
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]
        resources = response.data["data"]
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

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["success"]

        resource = response.data["data"]
        assert resource["title"] == "Cave Entrance Photo"
        assert resource["resource_type"] == StationResourceType.PHOTO
        assert resource["file_url"] is not None
        assert resource["created_by"] == self.user.email

    def test_create_video_resource(self) -> None:
        with Path("speleodb/api/v1/tests/artifacts/video.mp4").open(mode="rb") as f:
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

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["success"]

        resource = response.data["data"]
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

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["success"]

        resource = response.data["data"]
        assert resource["resource_type"] == StationResourceType.NOTE
        assert resource["text_content"] == data["text_content"]
        assert resource["file_url"] is None

    def test_create_sketch_resource(self) -> None:
        """Test creating a sketch resource."""
        svg_content = '<svg><circle cx="50" cy="50" r="40" /></svg>'
        data = {
            "resource_type": StationResourceType.SKETCH,
            "title": "Cave Map Sketch",
            "description": "Rough layout",
            "text_content": svg_content,
        }

        response = self.client.post(
            self.resource_url,
            data,
            format="json",
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["success"]

        resource = response.data["data"]
        assert resource["resource_type"] == StationResourceType.SKETCH
        assert resource["text_content"] == svg_content

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

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["success"]

        resource = response.data["data"]
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

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not response.data["success"]
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

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not response.data["success"]
        assert "requires text content" in str(response.data["errors"])

    def test_retrieve_resource(self) -> None:
        """Test retrieving a single resource."""
        resource = StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="Test Note",
            text_content="Content",
            created_by=self.user,
            station=self.station,
        )

        url = reverse("api:v1:resource-detail", kwargs={"id": resource.id})
        response = self.client.get(url, headers={"authorization": self.auth})

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]

        data = response.data["data"]
        assert data["id"] == str(resource.id)
        assert data["title"] == "Test Note"

    def test_update_resource(self) -> None:
        """Test updating a resource."""
        resource = StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="Old Title",
            text_content="Old content",
            created_by=self.user,
            station=self.station,
        )

        reverse("api:v1:resource-detail", kwargs={"id": resource.id})
        update_data = {
            "title": "New Title",
            "description": "Updated description",
            "text_content": "New content",
        }

        url = reverse("api:v1:resource-detail", kwargs={"id": resource.id})

        response = self.client.patch(
            url,
            update_data,
            format="json",
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]

        updated = response.data["data"]
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
            created_by=self.user,
            station=self.station,
        )

        # Update with new file
        new_image = self._create_test_image("new.jpg", size=(200, 200))
        update_data = {
            "title": "New Photo",
            "file": new_image,
        }

        url = reverse("api:v1:resource-detail", kwargs={"id": resource.id})

        response = self.client.patch(
            url, update_data, format="multipart", headers={"authorization": self.auth}
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]

        updated = response.data["data"]
        assert updated["title"] == "New Photo"
        assert "new.jpg" in updated["file_url"]

    def test_delete_resource(self) -> None:
        """Test deleting a resource."""
        resource = StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="To Delete",
            text_content="Content",
            created_by=self.user,
            station=self.station,
        )

        url = reverse("api:v1:resource-detail", kwargs={"id": resource.id})
        response = self.client.delete(url, headers={"authorization": self.auth})

        if self.level < PermissionLevel.ADMIN:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"]

        # Verify deletion
        assert not StationResource.objects.filter(id=resource.id).exists()

    def test_delete_resource_with_file(self) -> None:
        """Test deleting a resource also removes the file."""
        resource = StationResource.objects.create(
            resource_type=StationResourceType.PHOTO,
            title="Photo to Delete",
            file=self._create_test_image(),
            created_by=self.user,
            station=self.station,
        )
        resource_id = resource.id

        url = reverse("api:v1:resource-detail", kwargs={"id": resource.id})
        response = self.client.delete(url, headers={"authorization": self.auth})

        if self.level < PermissionLevel.ADMIN:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK

        # Verify resource is deleted
        assert not StationResource.objects.filter(id=resource_id).exists()

    def test_resource_ordering(self) -> None:
        """Test resources are returned in correct order by modified date."""
        # Create resources with different modified times
        StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="Third",
            text_content="3",
            created_by=self.user,
            station=self.station,
        )
        StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="First",
            text_content="1",
            created_by=self.user,
            station=self.station,
        )
        StationResource.objects.create(
            resource_type=StationResourceType.NOTE,
            title="Second",
            text_content="2",
            created_by=self.user,
            station=self.station,
        )

        response = self.client.get(
            self.resource_url,
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK

        resources = response.data["data"]

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
        self.station = StationFactory.create(project=self.project)

    def test_resource_list_requires_authentication(self) -> None:
        """Test that resource list endpoint requires authentication."""
        response = self.client.get(
            reverse("api:v1:station-resources", kwargs={"id": uuid.uuid4()})
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
                "api:v1:station-resources",
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
        self.station = StationFactory.create(project=self.project)

    def test_resource_create_permissions(self) -> None:
        """Test that readonly permissions cannot create resources."""

        data = {
            "resource_type": StationResourceType.NOTE,
            "title": "Test Note",
            "text_content": "This is a test note",
        }

        response = self.client.post(
            reverse(
                "api:v1:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        assert (
            response.status_code == status.HTTP_403_FORBIDDEN
            if self.level < PermissionLevel.READ_AND_WRITE
            else status.HTTP_201_CREATED
        )

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
                "api:v1:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_201_CREATED

        resource_data = response.data["data"]
        assert resource_data["resource_type"] == StationResourceType.NOTE
        assert resource_data["title"] == "Cave Survey Notes"
        assert resource_data["text_content"] == data["text_content"]

    def test_create_sketch_resource(self) -> None:
        """Test creating a sketch resource."""
        svg_content = """<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
            <circle cx="100" cy="100" r="50" fill="blue" stroke="black" stroke-width="2"/>
            <text x="100" y="105" text-anchor="middle" fill="white" font-size="14">Cave</text>
        </svg>"""  # noqa: E501

        data = {
            "resource_type": StationResourceType.SKETCH,
            "title": "Cave Entrance Sketch",
            "description": "Hand-drawn sketch of the cave entrance",
            "text_content": svg_content,
        }

        response = self.client.post(
            reverse(
                "api:v1:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_201_CREATED

        resource_data = response.data["data"]
        assert resource_data["resource_type"] == StationResourceType.SKETCH
        assert resource_data["title"] == "Cave Entrance Sketch"
        assert svg_content in resource_data["text_content"]

    def test_create_photo_resource_with_file(self) -> None:
        """Test creating a photo resource with file upload."""
        # Create a fake image file
        image_file = SimpleUploadedFile(
            "test_photo.jpg",
            Path("speleodb/api/v1/tests/artifacts/image.jpg").read_bytes(),
            content_type="image/jpeg",
        )

        data = {
            "resource_type": StationResourceType.PHOTO,
            "title": "Cave Entrance Photo",
            "description": "Photo taken at the main entrance",
            "file": image_file,
        }

        response = self.client.post(
            reverse(
                "api:v1:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_201_CREATED

        resource_data = response.data["data"]
        assert resource_data["resource_type"] == StationResourceType.PHOTO
        assert resource_data["title"] == "Cave Entrance Photo"
        assert resource_data["file"] is not None

    def test_list_station_resources(self) -> None:
        """Test listing resources for a station."""
        # Create multiple resources
        resources = [
            NoteStationResourceFactory.create(station=self.station),
            SketchStationResourceFactory.create(station=self.station),
            PhotoStationResourceFactory.create(station=self.station),
        ]

        response = self.client.get(
            reverse(
                "api:v1:station-resources",
                kwargs={"id": self.station.id},
            )
            + f"?station_id={self.station.id}",
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 3  # noqa: PLR2004

        # Verify all resources are present (without depending on order)
        response_resource_ids = {r["id"] for r in response.data["data"]}
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
                "api:v1:resource-detail",
                kwargs={"id": resource.id},
            ),
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK

        resource_data = response.data["data"]
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
                "api:v1:resource-detail",
                kwargs={"id": resource.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK

        resource_data = response.data["data"]
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
                "api:v1:resource-detail",
                kwargs={"id": resource.id},
            ),
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.ADMIN:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert "id" in response.data["data"]
        assert response.data["data"]["id"] == str(resource_id)

        # Verify resource was deleted
        assert not StationResource.objects.filter(id=resource_id).exists()


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
class TestStationResourceValidation(BaseAPIProjectTestCase):
    """Test validation for station resource data."""

    level: PermissionLevel
    permission_type: PermissionType
    station: Station

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=self.level, permission_type=self.permission_type
        )
        self.station = StationFactory.create(project=self.project)

    def test_create_resource_missing_title(self) -> None:
        """Test creating a resource without a title."""
        data = {
            "resource_type": StationResourceType.NOTE,
            "text_content": "Note without title",
        }

        response = self.client.post(
            reverse(
                "api:v1:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

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
                "api:v1:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "resource_type" in response.data["errors"]

    @parameterized.expand(
        [
            (StationResourceType.PHOTO, "test.jpg", "image/jpeg"),
            (StationResourceType.VIDEO, "test.mp4", "video/mp4"),
            (StationResourceType.DOCUMENT, "test.pdf", "application/pdf"),
        ]
    )
    def test_create_file_based_resources(
        self, resource_type: str, filename: str, content_type: str
    ) -> None:
        """Test creating file-based resources."""
        match resource_type:
            case StationResourceType.PHOTO:
                file_content = Path(
                    "speleodb/api/v1/tests/artifacts/image.jpg"
                ).read_bytes()
            case StationResourceType.VIDEO:
                file_content = Path(
                    "speleodb/api/v1/tests/artifacts/video.mp4"
                ).read_bytes()
            case StationResourceType.DOCUMENT:
                file_content = Path(
                    "speleodb/api/v1/tests/artifacts/document.pdf"
                ).read_bytes()
            case _:
                raise ValueError(f"Unexpected value received: {resource_type}")

        uploaded_file = SimpleUploadedFile(filename, file_content, content_type)

        data = {
            "resource_type": resource_type,
            "title": f"Test {resource_type.title()}",
            "description": f"Test {resource_type} file",
            "file": uploaded_file,
        }

        response = self.client.post(
            reverse(
                "api:v1:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_201_CREATED

        resource_data = response.data["data"]
        assert resource_data["resource_type"] == resource_type
        assert resource_data["file"] is not None

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
                "api:v1:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_400_BAD_REQUEST


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
class TestStationResourceFileHandling(BaseAPIProjectTestCase):
    """Test file handling for station resources."""

    level: PermissionLevel
    permission_type: PermissionType
    station: Station

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=self.level, permission_type=self.permission_type
        )
        self.station = StationFactory.create(project=self.project)

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
                "api:v1:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_201_CREATED

        # Retrieve the created resource
        resource = StationResource.objects.get(id=response.data["data"]["id"])

        # Read the stored file and verify checksum
        if resource.file:
            with resource.file.open("rb") as f:
                stored_content = f.read()

            actual_sha256 = hashlib.sha256(stored_content).hexdigest()
            assert actual_sha256 == expected_sha256, "File integrity check failed"

    def test_large_file_upload(self) -> None:
        """Test uploading a larger file."""
        # Create a 1MB test file
        large_content = b"A" * (1024 * 1024)  # 1MB of 'A' characters

        uploaded_file = SimpleUploadedFile(
            "large_test.dat", large_content, content_type="application/octet-stream"
        )

        data = {
            "resource_type": StationResourceType.DOCUMENT,
            "title": "Large Test File",
            "description": "Testing large file upload",
            "file": uploaded_file,
        }

        response = self.client.post(
            reverse(
                "api:v1:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        # Should either succeed or fail gracefully
        assert response.status_code == status.HTTP_400_BAD_REQUEST

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
                "api:v1:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

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
                "api:v1:station-resources",
                kwargs={"id": self.station.id},
            ),
            data=data,
            headers={"authorization": self.auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_400_BAD_REQUEST


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
class TestStationResourceFuzzing(BaseAPIProjectTestCase):
    """Fuzzy testing for station resource API endpoints."""

    level: PermissionLevel
    permission_type: PermissionType
    station: Station

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=self.level, permission_type=self.permission_type
        )
        self.station = StationFactory.create(project=self.project)
        self.faker = Faker()

    def test_fuzz_resource_data(self) -> None:
        """Test resource creation with various data types."""

        # Test with various data combinations
        fuzz_data_sets = [
            # Valid note data
            {
                "resource_type": StationResourceType.NOTE,
                "title": self.faker.sentence(),
                "text_content": self.faker.paragraph(),
            },
            # Edge case titles
            {
                "resource_type": StationResourceType.NOTE,
                "title": "A" * 200,  # Max length
                "text_content": "Test",
            },
            # Special characters in text
            {
                "resource_type": StationResourceType.NOTE,
                "title": "Special Characters: !@#$%^&*()",
                "text_content": "<script>alert('xss')</script>",
            },
            # Unicode content
            {
                "resource_type": StationResourceType.NOTE,
                "title": "Unicode Test: 中文测试 🎉",
                "text_content": "Unicode content: αβγδε",
            },
            # Very long text content
            {
                "resource_type": StationResourceType.NOTE,
                "title": "Long Content Test",
                "text_content": self.faker.text(max_nb_chars=10000),
            },
            # SVG sketch content
            {
                "resource_type": StationResourceType.SKETCH,
                "title": "SVG Test",
                "text_content": '<svg><rect x="0" y="0" width="100" height="100"/></svg>',  # noqa: E501
            },
            # Malformed SVG
            {
                "resource_type": StationResourceType.SKETCH,
                "title": "Malformed SVG",
                "text_content": '<svg><rect x="0" y="0" width="100"',  # Incomplete
            },
        ]

        for idx, data in enumerate(fuzz_data_sets):
            data.update({"station_id": str(self.station.id)})
            response = self.client.post(
                reverse(
                    "api:v1:station-resources",
                    kwargs={"id": self.station.id},
                ),
                data=data,
                headers={"authorization": self.auth},
            )

            if self.level < PermissionLevel.READ_AND_WRITE:
                assert response.status_code == status.HTTP_403_FORBIDDEN
                continue

            assert response.status_code == status.HTTP_201_CREATED, idx

    def test_fuzz_file_uploads_errors(self) -> None:
        """Test file uploads with various file types and content."""

        # Test various file scenarios
        file_tests = [
            # Valid image file
            (
                StationResourceType.PHOTO,
                "test.jpg",
                Path("speleodb/api/v1/tests/artifacts/image.jpg").read_bytes(),
                "image/jpeg",
                status.HTTP_201_CREATED,
            ),
            # Valid video file
            (
                StationResourceType.VIDEO,
                "test.mp4",
                Path("speleodb/api/v1/tests/artifacts/video.mp4").read_bytes(),
                "video/mp4",
                status.HTTP_201_CREATED,
            ),
            # Invalid file extension
            (
                StationResourceType.PHOTO,
                "test.jpoog",
                Path("speleodb/api/v1/tests/artifacts/image.jpg").read_bytes(),
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
                Path("speleodb/api/v1/tests/artifacts/document.pdf").read_bytes(),
                "application/pdf",
                status.HTTP_400_BAD_REQUEST,
            ),
            # Special characters in filename
            (
                StationResourceType.DOCUMENT,
                "test file with spaces & symbols!.pdf",
                Path("speleodb/api/v1/tests/artifacts/document.pdf").read_bytes(),
                "application/pdf",
                status.HTTP_201_CREATED,
            ),
            # Unicode filename
            (
                StationResourceType.DOCUMENT,
                "测试文件.pdf",
                Path("speleodb/api/v1/tests/artifacts/document.pdf").read_bytes(),
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
                    "api:v1:station-resources",
                    kwargs={"id": self.station.id},
                ),
                data=data,
                headers={"authorization": self.auth},
            )

            if self.level < PermissionLevel.READ_AND_WRITE:
                assert response.status_code == status.HTTP_403_FORBIDDEN
                continue

            assert response.status_code == expected_status, idx
