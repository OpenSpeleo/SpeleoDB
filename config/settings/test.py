# -*- coding: utf-8 -*-

"""
Test Django settings for SpeleoDB project.

- Use fast password hashing
- Use in-memory SQLite for tests
- Use temporary directory for media files
- Disable migrations where possible
"""

from __future__ import annotations

from .base import *  # noqa: F403
from .base import INSTALLED_APPS
from .base import TEMPLATES
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="LV2g9377n6a0Ihq09xPQYuiRT8ti5PHoDoh7d23s0xSlom1snTLhTuYXfAZnWOoI",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#test-runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# DEBUGGING FOR TEMPLATES
# ------------------------------------------------------------------------------
TEMPLATES[0]["OPTIONS"]["debug"] = True  # type: ignore[index]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "http://media.testserver/"

# django-extensions
# ------------------------------------------------------------------------------
# https://django-extensions.readthedocs.io/en/latest/installation_instructions.html#configuration
INSTALLED_APPS += ["django_extensions"]

# FILE STORAGE FOR TESTS
# ------------------------------------------------------------------------------
# Use temporary directory for tests
import os
import tempfile

# Respect environment variable for S3 usage in tests
USE_S3 = env.bool("USE_S3", default=False)

# Create a temporary directory for test media files (only used when USE_S3=False)
TEMP_MEDIA_ROOT = env(
    "LOCAL_MEDIA_ROOT", default=tempfile.mkdtemp(prefix="speleodb_test_")
)

# Only set MEDIA_ROOT for local storage
if not USE_S3:
    MEDIA_ROOT = TEMP_MEDIA_ROOT

# Ensure the directory exists for local storage
if not USE_S3:
    os.makedirs(MEDIA_ROOT, exist_ok=True)

# Clean up temp directory after tests (handled by pytest fixtures)
import atexit


def cleanup_temp_media():
    """Clean up temporary media directory."""
    import shutil

    if os.path.exists(TEMP_MEDIA_ROOT):
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)


atexit.register(cleanup_temp_media)

# Your stuff...
# ------------------------------------------------------------------------------
