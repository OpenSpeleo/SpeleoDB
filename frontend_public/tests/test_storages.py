# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import Any
from unittest import mock

from django.conf import settings
from django.test import TestCase

from frontend_public.storages import PersonPhotoStorage


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
