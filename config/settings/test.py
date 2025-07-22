# -*- coding: utf-8 -*-

"""
Test Django settings for SpeleoDB project.

- Use fast password hashing
- Use in-memory SQLite for tests
- Use temporary directory for media files
- Disable migrations where possible
"""

from __future__ import annotations

import atexit
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv


def load_env_files_from_pyproject() -> None:
    for env_file in [".envs/test.env"]:
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path, override=True)
        else:
            print(f"Warning: env file not found: `{env_path.resolve()}`")  # noqa: T201


# Ensures the .env files are loaded before anything else
load_env_files_from_pyproject()


from .base import *  # noqa: E402, F403
from .base import INSTALLED_APPS  # noqa: E402
from .base import TEMPLATES  # noqa: E402
from .base import env  # noqa: E402

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="LV2g9377n6a0Ihq09xPQYuiRT8ti5PHoDoh7d23s0xSlom1snTLhTuYXfAZnWOoI",  # pyright: ignore[reportArgumentType]
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
# Respect environment variable for S3 usage in tests
USE_S3 = env.bool("USE_S3", default=False)  # pyright: ignore[reportArgumentType]

# Create a temporary directory for test media files (only used when USE_S3=False)
TEMP_MEDIA_ROOT = env(
    "LOCAL_MEDIA_ROOT",
    default=tempfile.mkdtemp(prefix="speleodb_test_"),  # pyright: ignore[reportArgumentType]
)

# Only set MEDIA_ROOT for local storage
if not USE_S3:
    MEDIA_ROOT = TEMP_MEDIA_ROOT

# Ensure the directory exists for local storage
if not USE_S3:
    Path(MEDIA_ROOT).mkdir(parents=True, exist_ok=True)  # pyright: ignore[reportArgumentType]

# Clean up temp directory after tests (handled by pytest fixtures)


def cleanup_temp_media() -> None:
    """Clean up temporary media directory."""

    if Path(TEMP_MEDIA_ROOT).exists():  # pyright: ignore[reportArgumentType]
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)  # pyright: ignore[reportArgumentType]


atexit.register(cleanup_temp_media)

# Your stuff...
# ------------------------------------------------------------------------------
