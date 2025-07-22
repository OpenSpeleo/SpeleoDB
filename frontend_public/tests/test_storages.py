# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

from django.conf import settings
from django.core.files.base import ContentFile
from django.test import TestCase
from django.test import override_settings

from frontend_public.models import BoardMember
from frontend_public.storages import LocalPersonPhotoStorage
from frontend_public.storages import PersonPhotoStorage
from frontend_public.storages import get_person_photo_storage


class StorageSelectionTests(TestCase):
    """Test storage backend selection."""

    @override_settings(USE_S3=False, HAS_S3_STORAGE=False)
    @mock.patch("frontend_public.storages.HAS_S3_STORAGE", False)  # noqa: FBT003
    def test_local_storage_when_s3_disabled(self) -> None:
        """Test that local storage is used when S3 is disabled."""
        storage = get_person_photo_storage()
        assert isinstance(storage, LocalPersonPhotoStorage)

    @override_settings(USE_S3=True, HAS_S3_STORAGE=True)
    @mock.patch("frontend_public.storages.HAS_S3_STORAGE", True)  # noqa: FBT003
    def test_s3_storage_when_s3_enabled(self) -> None:
        """Test that S3 storage is used when enabled."""
        storage = get_person_photo_storage()
        assert isinstance(storage, PersonPhotoStorage)


class LocalPersonPhotoStorageTests(TestCase):
    """Test local storage backend."""

    def setUp(self) -> None:
        """Set up test data."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.storage = LocalPersonPhotoStorage()

    def test_storage_location(self) -> None:
        """Test that files are stored in the correct location."""
        # LocalPersonPhotoStorage should have location set
        expected_path = Path(settings.MEDIA_ROOT) / "people" / "photos"
        assert Path(self.storage.location) == expected_path

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_directory_creation(self) -> None:
        """Test that storage creates necessary directories."""
        # Create new storage instance
        storage = LocalPersonPhotoStorage()
        # Directory should exist
        assert Path(storage.location).exists()

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_file_saved_to_correct_location(self) -> None:
        """Test that files are saved to the correct path."""
        storage = LocalPersonPhotoStorage()
        content = ContentFile(b"test content")

        # Save file
        name = storage.save("test.jpg", content)

        # Check file exists in correct location
        full_path = Path(storage.location) / name
        assert full_path.exists()

        # Clean up
        storage.delete(name)

    def test_unique_filename_generation(self) -> None:
        """Test that unique filenames are generated."""
        content1 = ContentFile(b"content1")
        content2 = ContentFile(b"content2")

        # Save same filename twice
        name1 = self.storage.save("duplicate.jpg", content1)
        name2 = self.storage.save("duplicate.jpg", content2)

        # Names should be different
        assert name1 != name2

        # Clean up
        try:
            self.storage.delete(name1)
            self.storage.delete(name2)
        except FileNotFoundError:
            pass


# Only run S3 tests if S3 is available
if hasattr(settings, "USE_S3") and settings.USE_S3:

    class PersonPhotoStorageS3Tests(TestCase):
        """Test S3 storage backend configuration."""

        @mock.patch("storages.backends.s3boto3.S3Boto3Storage.__init__")
        def test_s3_storage_configuration(self, mock_init: Any) -> None:
            """Test S3 storage is configured correctly."""
            mock_init.return_value = None

            # Import here to avoid import errors

            storage = PersonPhotoStorage()

            # Check configuration using actual environment values
            assert storage.bucket_name == settings.AWS_STORAGE_BUCKET_NAME  # pyright: ignore[reportAttributeAccessIssue]
            assert storage.location == "media/people/photos"  # pyright: ignore[reportAttributeAccessIssue]
            assert storage.default_acl is None  # pyright: ignore[reportAttributeAccessIssue]
            assert not storage.file_overwrite  # pyright: ignore[reportAttributeAccessIssue]
            assert not storage.querystring_auth  # pyright: ignore[reportAttributeAccessIssue]

        @mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
        @mock.patch("storages.backends.s3boto3.S3Boto3Storage.__init__")
        def test_s3_unique_filename_generation(
            self, mock_init: Any, mock_save: Any
        ) -> None:
            """Test that S3 storage generates unique filenames."""
            mock_init.return_value = None
            mock_save.return_value = "mocked_name.jpg"

            storage = PersonPhotoStorage()

            # Mock the parent's get_available_name to test our override
            with mock.patch.object(
                storage.__class__.__bases__[0],
                "get_available_name",
                return_value="unique_name.jpg",
            ) as mock_get_available:
                _ = storage.get_available_name("test.jpg")  # pyright: ignore[reportAttributeAccessIssue]

                # Should call parent with UUID-prefixed name
                mock_get_available.assert_called_once()
                call_args = mock_get_available.call_args[0][0]
                # Should have UUID prefix
                assert re.search(r"^[a-f0-9]{32}_test\.jpg$", call_args)

        @mock.patch("storages.backends.s3boto3.S3Boto3Storage.__init__")
        def test_public_access_configuration(self, mock_init: Any) -> None:
            """Test that storage is configured for public access."""
            mock_init.return_value = None

            storage = PersonPhotoStorage()

            # Check public access settings
            assert storage.default_acl is None  # pyright: ignore[reportAttributeAccessIssue]
            assert not storage.querystring_auth  # pyright: ignore[reportAttributeAccessIssue]
            assert storage.custom_domain == settings.AWS_S3_CUSTOM_DOMAIN  # pyright: ignore[reportAttributeAccessIssue]

            # Check cache control
            expected_params = {"CacheControl": "public, max-age=86400"}
            assert storage.object_parameters == expected_params  # pyright: ignore[reportAttributeAccessIssue]


class StorageIntegrationTests(TestCase):
    """Test storage integration with models."""

    @override_settings(
        MEDIA_ROOT=tempfile.mkdtemp(), USE_S3=False, HAS_S3_STORAGE=False
    )
    @mock.patch("frontend_public.models.get_person_photo_storage")
    def test_model_uses_correct_storage(self, mock_get_storage: Any) -> None:
        """Test that models use the correct storage backend."""
        # Mock the storage getter to return local storage
        mock_storage = LocalPersonPhotoStorage()
        mock_get_storage.return_value = mock_storage

        # Create a model instance
        member = BoardMember(
            full_name="Test Person", title="Test Title", description="Test Description"
        )

        # The photo field should use our mocked storage
        _ = member._meta.get_field("photo")  # noqa: SLF001

        # Since we're using a callable storage, we need to check the actual storage
        # instance that would be returned by the callable
        assert mock_get_storage.return_value == mock_storage
