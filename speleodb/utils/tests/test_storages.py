# -*- coding: utf-8 -*-

from __future__ import annotations

import re

from django.conf import settings
from django.test import TestCase

from speleodb.utils.storages import PersonPhotoStorage
from speleodb.utils.storages import S3MediaStorage
from speleodb.utils.storages import StationResourceStorage


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


class StationResourceStorageTests(TestCase):
    """Test S3 storage backend configuration."""

    def test_s3_storage_configuration(self) -> None:
        """Test S3 storage is configured correctly."""

        storage = StationResourceStorage()

        # Check public access settings
        assert storage.default_acl == "private"
        assert not storage.file_overwrite
        assert not storage.custom_domain
        assert storage.location == "stations/resources"
        assert storage.bucket_name == settings.AWS_STORAGE_BUCKET_NAME

        # Check cache control
        expected_params = {"CacheControl": "public, max-age=86400"}
        assert storage.object_parameters == expected_params

    def test_s3_unique_filename_generation(self) -> None:
        """Test that S3 storage generates unique filenames."""

        storage = StationResourceStorage()

        name = storage.get_available_name("test.jpg")
        assert re.search(r"^[a-f0-9]{32}_test\.jpg$", name)

        name = storage.get_available_name("test.mp4")
        assert re.search(r"^[a-f0-9]{32}_test\.mp4$", name)

        name = storage.get_available_name("test.pdf")
        assert re.search(r"^[a-f0-9]{32}_test\.pdf$", name)
