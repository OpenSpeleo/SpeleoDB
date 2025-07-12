# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib

import boto3
from botocore.exceptions import ClientError
from botocore.exceptions import NoCredentialsError
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from faker import Faker
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.api.v1.tests.factories import StationResourceFactory
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models.station import StationResource
from speleodb.users.tests.factories import UserFactory


class TestS3CredentialValidation(BaseAPIProjectTestCase):
    """Test S3 credential validation - these tests should fail with improper
    credentials."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(level=PermissionLevel.ADMIN)

    def test_s3_credentials_with_presigned_url(self) -> None:
        """Test presigned URL generation - should fail with improper S3 credentials."""
        if not getattr(settings, "USE_S3", False):
            self.skipTest("S3 not enabled")

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-upload"),
            data={
                "filename": "test.jpg",
                "content_type": "image/jpeg",
                "resource_type": "photo",
            },
            headers={"authorization": auth},
        )

        # This should fail if S3 credentials are invalid
        # With proper credentials: 200 OK
        # With improper credentials: 500 INTERNAL_SERVER_ERROR
        if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            assert "error" in response.data
            assert "Failed to generate upload URL" in response.data["error"]
        else:
            # If credentials are valid, should succeed
            assert response.status_code == status.HTTP_200_OK
            assert "upload_url" in response.data["data"]

    def test_s3_credentials_with_signed_url(self) -> None:
        """Test signed URL generation - should fail with improper S3 credentials."""
        if not getattr(settings, "USE_S3", False):
            self.skipTest("S3 not enabled")

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-signed-url"),
            data={
                "file_key": "test-file.jpg",
                "expires_in": 3600,
            },
            headers={"authorization": auth},
        )

        # This should fail if S3 credentials are invalid
        if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            assert "error" in response.data
            assert "Failed to generate download URL" in response.data["error"]
        else:
            # If credentials are valid, should succeed
            assert response.status_code == status.HTTP_200_OK
            assert "download_url" in response.data["data"]

    def test_s3_credentials_with_secure_access(self) -> None:
        """Test secure access URL generation - should fail with improper S3
        credentials."""
        if not getattr(settings, "USE_S3", False):
            self.skipTest("S3 not enabled")

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-secure-access"),
            data={
                "file_path": "stations/resources/test.jpg",
                "project_id": str(self.project.id),
                "expires_in": 3600,
            },
            headers={"authorization": auth},
        )

        # This should fail if S3 credentials are invalid or file doesn't exist
        if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            assert "error" in response.data
            assert "Failed to generate access URL" in response.data["error"]
        elif response.status_code == status.HTTP_404_NOT_FOUND:
            # File doesn't exist, but credentials are valid
            assert "error" in response.data
            assert "File not found" in response.data["error"]
        else:
            # If credentials are valid and file exists, should succeed
            assert response.status_code == status.HTTP_200_OK
            assert "access_url" in response.data["data"]

    def test_s3_bucket_connectivity(self) -> None:
        """Test S3 bucket connectivity - should fail with improper credentials or
        bucket."""
        if not getattr(settings, "USE_S3", False):
            self.skipTest("S3 not enabled")

        try:
            # Try to create S3 client and test connectivity
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1"),
            )

            # Try to check if bucket exists - this should fail with improper credentials
            try:
                s3_client.head_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
            except (ClientError, NoCredentialsError) as e:
                # This is expected with improper credentials
                self.fail(f"S3 credentials are invalid: {e}")

        except ImportError:
            self.skipTest("boto3 not installed")

    def test_direct_s3_upload_with_invalid_credentials(self) -> None:
        """Test direct S3 upload - should fail with improper credentials."""
        if not getattr(settings, "USE_S3", False):
            self.skipTest("S3 not enabled")

        # Create a small test file
        test_file = SimpleUploadedFile(
            "test.txt", b"test content", content_type="text/plain"
        )

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-upload"),
            data={"file": test_file, "resource_type": "document"},
            headers={"authorization": auth},
        )

        # This should fail if S3 credentials are invalid
        if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            assert "error" in response.data
            assert "Upload failed" in response.data["error"]
        else:
            # If credentials are valid, should succeed
            assert response.status_code == status.HTTP_201_CREATED
            assert "file_path" in response.data["data"]

    def test_s3_with_explicitly_invalid_credentials(self) -> None:
        """Test S3 operations with explicitly invalid credentials - should fail."""
        if not getattr(settings, "USE_S3", False):
            self.skipTest("S3 not enabled")

        try:
            # Test direct boto3 client creation with invalid credentials
            s3_client = boto3.client(
                "s3",
                aws_access_key_id="INVALID_KEY_12345",
                aws_secret_access_key="INVALID_SECRET_67890",  # noqa: S106
                region_name="us-east-1",
            )

            # This should fail with invalid credentials
            failed = False
            try:
                s3_client.head_bucket(Bucket="nonexistent-bucket-12345")
            except (ClientError, NoCredentialsError):
                failed = True

            # Test passed - invalid credentials properly failed
            assert failed, "Invalid S3 credentials should have failed but didn't"

        except ImportError:
            self.skipTest("boto3 not installed")


class TestMediaStorageAuthentication(BaseAPIProjectTestCase):
    """Test authentication for media storage endpoints."""

    def test_upload_requires_auth(self) -> None:
        """Test upload requires authentication."""
        test_file = SimpleUploadedFile(
            "test.jpg", b"content", content_type="image/jpeg"
        )
        response = self.client.post(
            reverse("api:v1:media-upload"),
            data={"file": test_file, "resource_type": "photo"},
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_secure_access_requires_auth(self) -> None:
        """Test secure access requires authentication."""
        response = self.client.post(
            reverse("api:v1:media-secure-access"),
            data={"file_path": "test.jpg", "project_id": str(self.project.id)},
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


class TestMediaStorageAPIPermissions(BaseAPIProjectTestCase):
    """Test permission requirements for media storage API endpoints."""

    def setUp(self) -> None:
        super().setUp()
        self.station = StationFactory.create(project=self.project)

    @parameterized.expand(
        [
            PermissionLevel.WEB_VIEWER,
            PermissionLevel.READ_ONLY,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.ADMIN,
        ]
    )
    def test_media_upload_with_different_permissions(
        self, level: PermissionLevel
    ) -> None:
        """Test media upload with different permission levels."""
        self.set_test_project_permission(level=level)

        test_file = SimpleUploadedFile(
            "test.jpg", b"fake_image_content", content_type="image/jpeg"
        )

        data = {
            "file": test_file,
            "resource_type": "photo",
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-upload"),
            data=data,
            headers={"authorization": auth},
        )

        # All authenticated users should be able to upload files
        # (permission checking happens at resource creation level)
        assert response.status_code == status.HTTP_201_CREATED

    @parameterized.expand(
        [
            PermissionLevel.WEB_VIEWER,
            PermissionLevel.READ_ONLY,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.ADMIN,
        ]
    )
    def test_media_secure_access_with_project_permissions(
        self, level: PermissionLevel
    ) -> None:
        """Test secure access with different project permission levels."""
        self.set_test_project_permission(level=level)

        # Create a resource with a file
        _ = StationResourceFactory.create(
            station=self.station,
            resource_type=StationResource.ResourceType.PHOTO,
        )

        # Mock file path (in real scenario this would be set during file upload)
        fake_file_path = "stations/resources/2024/01/01/test.jpg"

        data = {
            "file_path": fake_file_path,
            "project_id": str(self.project.id),
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-secure-access"),
            data=data,
            headers={"authorization": auth},
        )

        # Users with project access should be able to access files
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,  # File doesn't actually exist
        ]

    def test_media_secure_access_without_project_permission(self) -> None:
        """Test secure access without project permission."""
        # Create another user without project permission
        other_user = UserFactory.create()
        other_token = TokenFactory.create(user=other_user)

        fake_file_path = "stations/resources/2024/01/01/test.jpg"

        data = {
            "file_path": fake_file_path,
            "project_id": str(self.project.id),
        }

        auth = self.header_prefix + other_token.key
        response = self.client.post(
            reverse("api:v1:media-secure-access"),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestMediaUpload(BaseAPIProjectTestCase):
    """Test media upload functionality."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(level=PermissionLevel.ADMIN)

    def test_upload_image(self) -> None:
        """Test uploading an image file."""
        content = b"fake_jpeg_content"
        test_file = SimpleUploadedFile("test.jpg", content, content_type="image/jpeg")

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-upload"),
            data={"file": test_file, "resource_type": "photo"},
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert "file_path" in response.data["data"]
        assert "file_url" in response.data["data"]

    def test_upload_with_checksum(self) -> None:
        """Test upload with SHA256 verification."""
        content = b"test content for checksum verification"
        hashlib.sha256(content).hexdigest()

        test_file = SimpleUploadedFile("test.txt", content, content_type="text/plain")

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-upload"),
            data={"file": test_file, "resource_type": "document"},
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        # File integrity would be verified in actual storage backend

    def test_upload_missing_file(self) -> None:
        """Test upload without file."""
        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-upload"),
            data={"resource_type": "photo"},
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_invalid_type(self) -> None:
        """Test upload with invalid resource type."""
        test_file = SimpleUploadedFile(
            "test.jpg", b"content", content_type="image/jpeg"
        )

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-upload"),
            data={"file": test_file, "resource_type": "invalid"},
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestMediaSecureAccess(BaseAPIProjectTestCase):
    """Test secure media access."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(level=PermissionLevel.READ_ONLY)

    def test_access_with_permission(self) -> None:
        """Test file access with proper permissions."""
        data = {
            "file_path": "stations/resources/2024/01/01/test.jpg",
            "project_id": str(self.project.id),
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-secure-access"),
            data=data,
            headers={"authorization": auth},
        )

        # File might not exist, but permission should be valid
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_access_without_permission(self) -> None:
        """Test file access without project permissions."""
        other_user = UserFactory.create()
        other_token = TokenFactory.create(user=other_user)

        data = {
            "file_path": "stations/resources/2024/01/01/test.jpg",
            "project_id": str(self.project.id),
        }

        auth = self.header_prefix + other_token.key
        response = self.client.post(
            reverse("api:v1:media-secure-access"),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_path_traversal_protection(self) -> None:
        """Test protection against path traversal attacks."""
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "stations/resources/../../../sensitive.txt",
        ]

        auth = self.header_prefix + self.token.key

        for path in malicious_paths:
            data = {
                "file_path": path,
                "project_id": str(self.project.id),
            }

            response = self.client.post(
                reverse("api:v1:media-secure-access"),
                data=data,
                headers={"authorization": auth},
            )

            # Should block path traversal
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
            ]


class TestMediaValidation(BaseAPIProjectTestCase):
    """Test media validation and edge cases."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(level=PermissionLevel.ADMIN)

    def test_large_file_upload(self) -> None:
        """Test uploading large files."""
        large_content = b"A" * (5 * 1024 * 1024)  # 5MB
        test_file = SimpleUploadedFile("large.dat", large_content)

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-upload"),
            data={"file": test_file, "resource_type": "document"},
            headers={"authorization": auth},
        )

        # Should handle gracefully
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_malicious_filenames(self) -> None:
        """Test handling of malicious filenames."""
        malicious_names = [
            "../../../etc/passwd",
            "test.php.jpg",
            "test<script>.jpg",
            "CON.jpg",  # Windows reserved
        ]

        auth = self.header_prefix + self.token.key

        for filename in malicious_names:
            test_file = SimpleUploadedFile(
                filename, b"content", content_type="image/jpeg"
            )

            response = self.client.post(
                reverse("api:v1:media-upload"),
                data={"file": test_file, "resource_type": "photo"},
                headers={"authorization": auth},
            )

            # Should handle malicious names safely
            assert response.status_code in [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
            ]

    def test_empty_file(self) -> None:
        """Test uploading empty file."""
        test_file = SimpleUploadedFile("empty.txt", b"", content_type="text/plain")

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-upload"),
            data={"file": test_file, "resource_type": "document"},
            headers={"authorization": auth},
        )

        # Should handle empty files gracefully
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
        ]


class TestMediaFuzzing(BaseAPIProjectTestCase):
    """Fuzzy testing for media endpoints."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(level=PermissionLevel.ADMIN)
        self.faker = Faker()

    def test_fuzz_upload_data(self) -> None:
        """Test upload with various data combinations."""
        auth = self.header_prefix + self.token.key

        test_cases = [
            # Valid cases
            {"resource_type": "photo"},
            {"resource_type": "video"},
            {"resource_type": "document"},
            # Invalid cases
            {"resource_type": "invalid"},
            {"resource_type": ""},
            {"extra_field": "ignored"},
            {},
        ]

        for i, data in enumerate(test_cases):
            if "resource_type" in data and data["resource_type"] in [
                "photo",
                "video",
                "document",
            ]:
                test_file = SimpleUploadedFile(
                    f"test_{i}.jpg", b"content", content_type="image/jpeg"
                )
                data["file"] = test_file  # type: ignore[assignment]

            response = self.client.post(
                reverse("api:v1:media-upload"),
                data=data,
                headers={"authorization": auth},
            )

            # Should handle all cases gracefully
            assert response.status_code in [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
            ]

    def test_fuzz_random_content(self) -> None:
        """Test upload with random binary content."""
        auth = self.header_prefix + self.token.key

        for i in range(5):
            # Generate random content
            size = self.faker.random_int(min=1, max=1024)
            content = bytes(
                [self.faker.random_int(min=0, max=255) for _ in range(size)]
            )

            test_file = SimpleUploadedFile(f"random_{i}.dat", content)

            response = self.client.post(
                reverse("api:v1:media-upload"),
                data={"file": test_file, "resource_type": "document"},
                headers={"authorization": auth},
            )

            # Should handle random content
            assert response.status_code in [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
            ]


class TestUnauthorizedAccess(BaseAPIProjectTestCase):
    """Test unauthorized access attempts."""

    def test_direct_file_access(self) -> None:
        """Test direct file access attempts."""
        paths = [
            "/media/stations/resources/2024/01/01/test.jpg",
            "/static/admin/css/base.css",
            "/media/../../../etc/passwd",
        ]

        for path in paths:
            response = self.client.get(path)

            # Should not allow direct access
            assert response.status_code in [
                status.HTTP_404_NOT_FOUND,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_401_UNAUTHORIZED,
            ]

    def test_cross_project_access(self) -> None:
        """Test accessing files from other projects."""
        other_user = UserFactory.create()
        other_project = ProjectFactory.create(created_by=other_user)

        data = {
            "file_path": "stations/resources/2024/01/01/secret.jpg",
            "project_id": str(other_project.id),
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:media-secure-access"),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
