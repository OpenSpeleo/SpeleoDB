# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from urllib.parse import parse_qs
from urllib.parse import urlparse

from django.conf import settings
from django.test import TestCase

from speleodb.utils.s3_storages import AttachmentStorage
from speleodb.utils.s3_storages import GeoJSONStorage
from speleodb.utils.s3_storages import PersonPhotoStorage
from speleodb.utils.s3_storages import S3MediaStorage


class PersonPhotoStorageS3Tests(TestCase):
    """Test S3 storage backend configuration."""

    def test_s3_storage_configuration(self) -> None:
        """Test S3 storage is configured correctly."""

        storage = PersonPhotoStorage()

        # Check public access settings
        assert storage.default_acl is None
        assert not storage.querystring_auth
        assert not storage.file_overwrite
        assert storage.location == "media/people/photos"
        assert storage.bucket_name == settings.AWS_STORAGE_BUCKET_NAME
        assert storage.custom_domain == settings.AWS_S3_CUSTOM_DOMAIN

        # Check cache control
        expected_params = {"CacheControl": "public, max-age=86400"}
        assert storage.object_parameters == expected_params

    def test_s3_unique_filename_generation(self) -> None:
        """Test that S3 storage generates unique filenames."""

        storage = PersonPhotoStorage()

        name = storage.get_available_name("test.jpg")
        assert re.search(r"^[a-f0-9]{32}_test\.jpg$", name)


class S3MediaStorageTests(TestCase):
    """Test S3 storage backend configuration."""

    def test_s3_storage_configuration(self) -> None:
        """Test S3 storage is configured correctly."""

        storage = S3MediaStorage()

        # Check public access settings
        assert storage.default_acl == "private"
        assert not storage.file_overwrite
        assert not storage.custom_domain
        assert storage.location == "media/default"
        assert storage.bucket_name == settings.AWS_STORAGE_BUCKET_NAME

        # Check cache control
        expected_params = {"CacheControl": "public, max-age=86400"}
        assert storage.object_parameters == expected_params

    def test_s3_unique_filename_generation(self) -> None:
        """Test that S3 storage generates unique filenames."""

        storage = S3MediaStorage()

        name = storage.get_available_name("test.jpg")
        assert re.search(r"^[a-f0-9]{32}_test\.jpg$", name)


class AttachmentStorageTests(TestCase):
    """Test S3 storage backend configuration."""

    def test_s3_storage_configuration(self) -> None:
        """Test S3 storage is configured correctly."""

        storage = AttachmentStorage()

        # Check public access settings
        assert storage.default_acl == "private"
        assert not storage.file_overwrite
        assert not storage.custom_domain
        assert storage.location == "attachments"
        assert storage.bucket_name == settings.AWS_STORAGE_BUCKET_NAME

        # Check cache control
        expected_params = {"CacheControl": "public, max-age=86400"}
        assert storage.object_parameters == expected_params

    def test_s3_unique_filename_generation(self) -> None:
        """Test that S3 storage does not modify filenames."""

        storage = AttachmentStorage()

        for filename in ["test.jpg", "test.mp4", "test.pdf"]:
            assert storage.get_available_name(filename) == filename


class S3PresignedURLTests(TestCase):
    def test_geojson_url_uses_signature_version_4(self) -> None:
        storage = GeoJSONStorage()

        url = storage.url("project/commit/test.geojson")
        query = parse_qs(urlparse(url).query)

        assert settings.AWS_S3_SIGNATURE_VERSION == "s3v4"
        assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
