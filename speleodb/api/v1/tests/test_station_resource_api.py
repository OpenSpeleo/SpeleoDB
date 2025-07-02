# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from faker import Faker
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.factories import NoteStationResourceFactory
from speleodb.api.v1.tests.factories import PhotoStationResourceFactory
from speleodb.api.v1.tests.factories import SketchStationResourceFactory
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models.station import Station
from speleodb.surveys.models.station import StationResource


class TestStationResourceAPIAuthentication(BaseAPIProjectTestCase):
    """Test authentication requirements for station resource API endpoints."""

    station: Station

    def setUp(self) -> None:
        super().setUp()
        self.station = StationFactory.create(project=self.project)

    def test_resource_list_requires_authentication(self) -> None:
        """Test that resource list endpoint requires authentication."""
        response = self.client.get(
            reverse(
                "api:v1:resource-list-create",
            )
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_resource_create_requires_authentication(self) -> None:
        """Test that resource create endpoint requires authentication."""
        data = {
            "station_id": str(self.station.id),
            "resource_type": "note",
            "title": "Test Note",
            "text_content": "This is a test note",
        }
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


class TestStationResourceAPIPermissions(BaseAPIProjectTestCase):
    station: Station

    """Test permission requirements for station resource API endpoints."""

    def setUp(self) -> None:
        super().setUp()
        self.station = StationFactory.create(project=self.project)

    @parameterized.expand([PermissionLevel.WEB_VIEWER, PermissionLevel.READ_ONLY])
    def test_resource_create_forbidden_for_readonly_permissions(
        self, level: PermissionLevel
    ) -> None:
        """Test that readonly permissions cannot create resources."""
        self.set_test_project_permission(level=level)

        data = {
            "station_id": str(self.station.id),
            "resource_type": "note",
            "title": "Test Note",
            "text_content": "This is a test note",
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @parameterized.expand([PermissionLevel.READ_AND_WRITE, PermissionLevel.ADMIN])
    def test_resource_create_allowed_for_write_permissions(
        self, level: PermissionLevel
    ) -> None:
        """Test that write permissions can create resources."""
        self.set_test_project_permission(level=level)

        data = {
            "station_id": str(self.station.id),
            "resource_type": "note",
            "title": "Test Note",
            "text_content": "This is a test note",
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_resource_wrong_station(self) -> None:
        """Test that users cannot create resources on stations from projects they don't have access to."""
        # Create another project and station that the user doesn't have access to
        from speleodb.api.v1.tests.factories import ProjectFactory

        other_project = ProjectFactory.create()  # No permissions granted to self.user
        other_station = StationFactory.create(project=other_project)

        # Try to create a resource on the other station
        data = {
            "station_id": str(other_station.id),
            "resource_type": "note",
            "title": "Unauthorized Resource",
            "text_content": "This should not be allowed",
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        # Should be forbidden since user has no permissions on the other project
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Verify no resource was created
        assert not StationResource.objects.filter(station=other_station).exists()


class TestStationResourceCRUD(BaseAPIProjectTestCase):
    """Test CRUD operations for station resources."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(level=PermissionLevel.ADMIN)
        self.station = StationFactory.create(project=self.project)

    def test_create_note_resource(self) -> None:
        """Test creating a note resource."""
        data = {
            "station_id": str(self.station.id),
            "resource_type": "note",
            "title": "Cave Survey Notes",
            "description": "Detailed observations from the survey",
            "text_content": "The cave entrance is approximately 2m wide and 1.5m high. Temperature is constant at around 12°C.",
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED

        resource_data = response.data["data"]["resource"]
        assert resource_data["resource_type"] == "note"
        assert resource_data["title"] == "Cave Survey Notes"
        assert resource_data["text_content"] == data["text_content"]

    def test_create_sketch_resource(self) -> None:
        """Test creating a sketch resource."""
        svg_content = """<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
            <circle cx="100" cy="100" r="50" fill="blue" stroke="black" stroke-width="2"/>
            <text x="100" y="105" text-anchor="middle" fill="white" font-size="14">Cave</text>
        </svg>"""

        data = {
            "station_id": str(self.station.id),
            "resource_type": "sketch",
            "title": "Cave Entrance Sketch",
            "description": "Hand-drawn sketch of the cave entrance",
            "text_content": svg_content,
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED

        resource_data = response.data["data"]["resource"]
        assert resource_data["resource_type"] == "sketch"
        assert resource_data["title"] == "Cave Entrance Sketch"
        assert svg_content in resource_data["text_content"]

    def test_create_photo_resource_with_file(self) -> None:
        """Test creating a photo resource with file upload."""
        # Create a fake image file
        image_content = b"fake_image_content_for_testing"
        image_file = SimpleUploadedFile(
            "test_photo.jpg", image_content, content_type="image/jpeg"
        )

        data = {
            "station_id": str(self.station.id),
            "resource_type": "photo",
            "title": "Cave Entrance Photo",
            "description": "Photo taken at the main entrance",
            "file": image_file,
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED

        resource_data = response.data["data"]["resource"]
        assert resource_data["resource_type"] == "photo"
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

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:resource-list-create",
            )
            + f"?station_id={self.station.id}",
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]["resources"]) == 3

        # Verify all resources are present (without depending on order)
        response_resource_ids = {r["id"] for r in response.data["data"]["resources"]}
        expected_resource_ids = {str(r.id) for r in resources}
        assert response_resource_ids == expected_resource_ids

    def test_get_resource_detail(self) -> None:
        """Test getting resource detail."""
        resource = NoteStationResourceFactory.create(
            station=self.station,
            title="Detailed Note",
            text_content="This is a detailed note about the cave survey.",
        )

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:resource-detail",
                kwargs={"id": resource.id},
            ),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK

        resource_data = response.data["data"]["resource"]
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

        auth = self.header_prefix + self.token.key
        response = self.client.patch(
            reverse(
                "api:v1:resource-detail",
                kwargs={"id": resource.id},
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK

        resource_data = response.data["data"]["resource"]
        assert resource_data["title"] == "Updated Note Title"
        assert resource_data["description"] == "Updated description"
        assert (
            resource_data["text_content"] == "Updated note content with more details."
        )

    def test_delete_resource(self) -> None:
        """Test deleting a resource."""
        resource = NoteStationResourceFactory.create(station=self.station)
        resource_id = resource.id

        auth = self.header_prefix + self.token.key
        response = self.client.delete(
            reverse(
                "api:v1:resource-detail",
                kwargs={"id": resource.id},
            ),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data["data"]
        assert "deleted successfully" in response.data["data"]["message"]

        # Verify resource was deleted
        assert not StationResource.objects.filter(id=resource_id).exists()


class TestStationResourceValidation(BaseAPIProjectTestCase):
    """Test validation for station resource data."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(level=PermissionLevel.ADMIN)
        self.station = StationFactory.create(project=self.project)

    def test_create_resource_missing_title(self) -> None:
        """Test creating a resource without a title."""
        data = {
            "station_id": str(self.station.id),
            "resource_type": "note",
            "text_content": "Note without title",
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "title" in response.data["errors"]

    def test_create_resource_invalid_type(self) -> None:
        """Test creating a resource with invalid type."""
        data = {
            "station_id": str(self.station.id),
            "resource_type": "invalid_type",
            "title": "Invalid Resource",
            "text_content": "This has an invalid type",
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "resource_type" in response.data["errors"]

    @parameterized.expand(
        [
            ("photo", "test.jpg", "image/jpeg"),
            ("video", "test.mp4", "video/mp4"),
            ("document", "test.pdf", "application/pdf"),
        ]
    )
    def test_create_file_based_resources(
        self, resource_type: str, filename: str, content_type: str
    ) -> None:
        """Test creating file-based resources."""
        file_content = b"fake_file_content_for_testing"
        uploaded_file = SimpleUploadedFile(filename, file_content, content_type)

        data = {
            "station_id": str(self.station.id),
            "resource_type": resource_type,
            "title": f"Test {resource_type.title()}",
            "description": f"Test {resource_type} file",
            "file": uploaded_file,
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED

        resource_data = response.data["data"]["resource"]
        assert resource_data["resource_type"] == resource_type
        assert resource_data["file"] is not None

    def test_create_resource_title_too_long(self) -> None:
        """Test creating a resource with title too long."""
        long_title = "A" * 201  # Exceeds max length of 200
        data = {
            "station_id": str(self.station.id),
            "resource_type": "note",
            "title": long_title,
            "text_content": "Note with very long title",
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestStationResourceFileHandling(BaseAPIProjectTestCase):
    """Test file handling for station resources."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(level=PermissionLevel.ADMIN)
        self.station = StationFactory.create(project=self.project)

    def test_file_upload_with_checksum_verification(self) -> None:
        """Test file upload with SHA256 checksum verification."""
        # Create a test file with known content
        test_content = b"This is a test file for checksum verification. It contains specific data that will produce a predictable SHA256 hash."
        expected_sha256 = hashlib.sha256(test_content).hexdigest()

        uploaded_file = SimpleUploadedFile(
            "test_checksum.txt", test_content, content_type="text/plain"
        )

        data = {
            "station_id": str(self.station.id),
            "resource_type": "document",
            "title": "Checksum Test Document",
            "description": "Document for testing file integrity",
            "file": uploaded_file,
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED

        # Retrieve the created resource
        resource = StationResource.objects.get(
            id=response.data["data"]["resource"]["id"]
        )

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
            "station_id": str(self.station.id),
            "resource_type": "document",
            "title": "Large Test File",
            "description": "Testing large file upload",
            "file": uploaded_file,
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        # Should either succeed or fail gracefully
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_invalid_file_extension(self) -> None:
        """Test uploading file with invalid extension."""
        # Try uploading a file with disallowed extension
        uploaded_file = SimpleUploadedFile(
            "test.exe",  # Executable file not allowed
            b"fake_executable_content",
            content_type="application/x-executable",
        )

        data = {
            "station_id": str(self.station.id),
            "resource_type": "document",
            "title": "Invalid File Type",
            "description": "Testing invalid file extension",
            "file": uploaded_file,
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
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
            "station_id": str(self.station.id),
            "resource_type": "document",
            "title": "Empty File",
            "description": "Testing empty file upload",
            "file": uploaded_file,
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        # Should handle empty files gracefully
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
        ]


class TestStationResourceFuzzing(BaseAPIProjectTestCase):
    """Fuzzy testing for station resource API endpoints."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(level=PermissionLevel.ADMIN)
        self.station = StationFactory.create(project=self.project)
        self.faker = Faker()

    def test_fuzz_resource_data(self) -> None:
        """Test resource creation with various data types."""
        auth = self.header_prefix + self.token.key

        # Test with various data combinations
        fuzz_data_sets = [
            # Valid note data
            {
                "resource_type": "note",
                "title": self.faker.sentence(),
                "text_content": self.faker.paragraph(),
            },
            # Edge case titles
            {
                "resource_type": "note",
                "title": "A" * 200,  # Max length
                "text_content": "Test",
            },
            # Special characters in text
            {
                "resource_type": "note",
                "title": "Special Characters: !@#$%^&*()",
                "text_content": "<script>alert('xss')</script>",
            },
            # Unicode content
            {
                "resource_type": "note",
                "title": "Unicode Test: 中文测试 🎉",
                "text_content": "Unicode content: αβγδε",
            },
            # Very long text content
            {
                "resource_type": "note",
                "title": "Long Content Test",
                "text_content": self.faker.text(max_nb_chars=10000),
            },
            # SVG sketch content
            {
                "resource_type": "sketch",
                "title": "SVG Test",
                "text_content": '<svg><rect x="0" y="0" width="100" height="100"/></svg>',
            },
            # Malformed SVG
            {
                "resource_type": "sketch",
                "title": "Malformed SVG",
                "text_content": '<svg><rect x="0" y="0" width="100"',  # Incomplete
            },
        ]

        for i, data in enumerate(fuzz_data_sets):
            response = self.client.post(
                reverse(
                    "api:v1:resource-list-create",
                ),
                data=data,
                headers={"authorization": auth},
            )

            # Should either succeed or fail gracefully
            assert response.status_code in [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
            ], f"Failed on dataset {i}: {data}"

    def test_fuzz_file_uploads(self) -> None:
        """Test file uploads with various file types and content."""
        auth = self.header_prefix + self.token.key

        # Test various file scenarios
        file_tests = [
            # Valid image file
            ("photo", "test.jpg", b"fake_jpeg_content", "image/jpeg"),
            # Valid video file
            ("video", "test.mp4", b"fake_mp4_content", "video/mp4"),
            # Valid document
            ("document", "test.pdf", b"fake_pdf_content", "application/pdf"),
            # File with wrong extension for content type
            ("photo", "test.jpg", b"not_really_an_image", "text/plain"),
            # Very long filename
            ("document", "a" * 200 + ".txt", b"content", "text/plain"),
            # Special characters in filename
            (
                "document",
                "test file with spaces & symbols!.txt",
                b"content",
                "text/plain",
            ),
            # Unicode filename
            ("document", "测试文件.txt", b"content", "text/plain"),
        ]

        for resource_type, filename, content, content_type in file_tests:
            uploaded_file = SimpleUploadedFile(filename, content, content_type)

            data = {
                "station_id": str(self.station.id),
                "resource_type": resource_type,
                "title": f"Fuzz Test: {filename}",
                "file": uploaded_file,
            }

            response = self.client.post(
                reverse(
                    "api:v1:resource-list-create",
                ),
                data=data,
                headers={"authorization": auth},
            )

            # Should handle all file types gracefully
            assert response.status_code in [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
            ]
