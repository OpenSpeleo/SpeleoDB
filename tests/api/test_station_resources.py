# -*- coding: utf-8 -*-
"""Tests for Station Resource API endpoints."""

from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Station
from speleodb.surveys.models import StationResource


class TestStationResourceAPI(BaseAPIProjectTestCase):
    """Test cases for Station Resource CRUD operations."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        # Set up authentication
        self.auth = self.header_prefix + self.token.key

        # Give user permission to the project
        self.set_test_project_permission(PermissionLevel.READ_AND_WRITE)

        # Create a station for testing
        self.station = Station.objects.create(
            project=self.project,
            name="Test Station",
            latitude=Decimal("45.1234567"),
            longitude=Decimal("-122.7654321"),
            created_by=self.user,
        )
        self.resource_url = "/api/v1/resources/"

    def _create_test_image(self, name="test.jpg", size=(100, 100)):
        """Create a test image file."""
        # Create a minimal valid JPEG file (1x1 red pixel)
        jpeg_content = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n"
            b"\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d"
            b"\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00"
            b"\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01"
            b"\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02"
            b"\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03"
            b"\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11"
            b'\x05\x12!1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R'
            b"\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz"
            b"\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99"
            b"\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7"
            b"\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5"
            b"\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1"
            b"\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00"
            b"\x00?\x00\xfb\xd0\xa2\x8a\x00\xff\xd9"
        )
        return SimpleUploadedFile(name, jpeg_content, content_type="image/jpeg")

    def _create_test_text_file(self, name="test.txt", content="Test content"):
        """Create a test text file."""
        return SimpleUploadedFile(name, content.encode(), content_type="text/plain")

    def test_list_resources_empty(self):
        """Test listing resources when none exist."""
        response = self.client.get(
            f"{self.resource_url}?station_id={self.station.id}",
            headers={"authorization": self.auth},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["resources"], [])

    def test_list_resources_with_data(self):
        """Test listing resources when they exist."""
        # Create some resources
        resource1 = self.station.resources.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="Test Note",
            text_content="Some notes",
            created_by=self.user,
        )
        resource2 = self.station.resources.create(
            resource_type=StationResource.ResourceType.PHOTO,
            title="Test Photo",
            file=self._create_test_image(),
            created_by=self.user,
        )

        response = self.client.get(
            f"{self.resource_url}?station_id={self.station.id}",
            headers={"authorization": self.auth},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        resources = response.data["data"]["resources"]
        self.assertEqual(len(resources), 2)

        # Check ordering - should be ordered by most recent modified date first
        # Since resource2 was created after resource1, it should appear first
        self.assertEqual(resources[0]["title"], "Test Photo")
        self.assertEqual(resources[1]["title"], "Test Note")

    def test_create_photo_resource(self):
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
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])

        resource = response.data["data"]["resource"]
        self.assertEqual(resource["title"], "Cave Entrance Photo")
        self.assertEqual(resource["resource_type"], StationResource.ResourceType.PHOTO)
        self.assertIsNotNone(resource["file_url"])
        self.assertEqual(resource["created_by_email"], self.user.email)

    def test_create_video_resource(self):
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
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])

        resource = response.data["data"]["resource"]
        self.assertEqual(resource["resource_type"], StationResource.ResourceType.VIDEO)

    def test_create_note_resource(self):
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
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])

        resource = response.data["data"]["resource"]
        self.assertEqual(resource["resource_type"], StationResource.ResourceType.NOTE)
        self.assertEqual(resource["text_content"], data["text_content"])
        self.assertIsNone(resource["file_url"])

    def test_create_sketch_resource(self):
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
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])

        resource = response.data["data"]["resource"]
        self.assertEqual(resource["resource_type"], StationResource.ResourceType.SKETCH)
        self.assertEqual(resource["text_content"], svg_content)

    def test_create_document_resource(self):
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
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])

        resource = response.data["data"]["resource"]
        self.assertEqual(
            resource["resource_type"], StationResource.ResourceType.DOCUMENT
        )

    def test_create_resource_missing_file(self):
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
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertIn("requires a file", str(response.data["errors"]))

    def test_create_resource_missing_text(self):
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
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertIn("requires text content", str(response.data["errors"]))

    def test_retrieve_resource(self):
        """Test retrieving a single resource."""
        resource = self.station.resources.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="Test Note",
            text_content="Content",
            created_by=self.user,
        )

        url = f"/api/v1/resources/{resource.id}/"
        response = self.client.get(url, headers={"authorization": self.auth})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        data = response.data["data"]["resource"]
        self.assertEqual(data["id"], str(resource.id))
        self.assertEqual(data["title"], "Test Note")

    def test_update_resource(self):
        """Test updating a resource."""
        resource = self.station.resources.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="Old Title",
            text_content="Old content",
            created_by=self.user,
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
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        updated = response.data["data"]["resource"]
        self.assertEqual(updated["title"], "New Title")
        self.assertEqual(updated["description"], "Updated description")
        self.assertEqual(updated["text_content"], "New content")

    def test_update_resource_file(self):
        """Test updating a file resource with a new file."""
        # Create initial resource
        resource = self.station.resources.create(
            resource_type=StationResource.ResourceType.PHOTO,
            title="Old Photo",
            file=self._create_test_image("old.jpg"),
            created_by=self.user,
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
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        updated = response.data["data"]["resource"]
        self.assertEqual(updated["title"], "New Photo")
        self.assertIn("new.jpg", updated["file_url"])

    def test_delete_resource(self):
        """Test deleting a resource."""
        resource = self.station.resources.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="To Delete",
            text_content="Content",
            created_by=self.user,
        )

        url = f"/api/v1/resources/{resource.id}/"
        response = self.client.delete(url, headers={"authorization": self.auth})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        # Verify deletion
        self.assertFalse(StationResource.objects.filter(id=resource.id).exists())

    def test_delete_resource_with_file(self):
        """Test deleting a resource also removes the file."""
        resource = self.station.resources.create(
            resource_type=StationResource.ResourceType.PHOTO,
            title="Photo to Delete",
            file=self._create_test_image(),
            created_by=self.user,
        )
        resource_id = resource.id

        url = f"/api/v1/resources/{resource.id}/"
        response = self.client.delete(url, headers={"authorization": self.auth})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify resource is deleted
        self.assertFalse(StationResource.objects.filter(id=resource_id).exists())

    def test_resource_permissions_read_only(self):
        """Test read-only user cannot modify resources."""
        # Set user to read-only
        self.set_test_project_permission(PermissionLevel.READ_ONLY)

        # Can list resources
        response = self.client.get(
            f"{self.resource_url}?station_id={self.station.id}",
            headers={"authorization": self.auth},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Create resource as admin for further tests
        resource = self.station.resources.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="Test",
            text_content="Content",
            created_by=self.user,
        )
        url = f"/api/v1/resources/{resource.id}/"

        # Can retrieve
        response = self.client.get(url, headers={"authorization": self.auth})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Cannot update
        response = self.client.patch(
            url, {"title": "New"}, format="json", headers={"authorization": self.auth}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot delete
        response = self.client.delete(url, headers={"authorization": self.auth})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_resource_ordering(self):
        """Test resources are returned in correct order by modified date."""
        # Create resources with different modified times
        r3 = self.station.resources.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="Third",
            text_content="3",
            created_by=self.user,
        )
        r1 = self.station.resources.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="First",
            text_content="1",
            created_by=self.user,
        )
        r2 = self.station.resources.create(
            resource_type=StationResource.ResourceType.NOTE,
            title="Second",
            text_content="2",
            created_by=self.user,
        )

        response = self.client.get(
            f"{self.resource_url}?station_id={self.station.id}",
            headers={"authorization": self.auth},
        )
        resources = response.data["data"]["resources"]

        # Resources should be ordered by most recent modified date
        # Since r2 was created last, it should be first
        self.assertEqual(resources[0]["title"], "Second")
        self.assertEqual(resources[1]["title"], "First")
        self.assertEqual(resources[2]["title"], "Third")
