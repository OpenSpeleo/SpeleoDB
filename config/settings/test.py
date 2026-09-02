# -*- coding: utf-8 -*-

"""
Test Django settings for SpeleoDB project.

- Use fast password hashing
- Use in-memory SQLite for tests
- Use temporary directory for media files
- Disable migrations where possible
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


def load_env_files_from_pyproject() -> None:
    for env_file in [".envs/test.env"]:
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path, override=True)
        else:
            print(  # noqa: T201
                f"Warning: env file not found: `{env_path.resolve()}`",
                file=sys.stderr,
            )


# Ensures the .env files are loaded before anything else
load_env_files_from_pyproject()


from .base import *  # noqa: E402, F403
from .base import AWS_STORAGE_BUCKET_NAME  # noqa: E402
from .base import INSTALLED_APPS  # noqa: E402
from .base import TEMPLATES  # noqa: E402
from .base import env  # noqa: E402

# Have to overwrite because of `USE_DOCKER` in base.py
DATABASES = {"default": env.db("DATABASE_URL")}
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",  # Your regular database file
#         "TEST": {
#             "NAME": BASE_DIR / "test_db.sqlite3",  # A separate file for tests
#         },
#     }
# }

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="LV2g9377n6a0Ihq09xPQYuiRT8ti5PHoDoh7d23s0xSlom1snTLhTuYXfAZnWOoI",  # pyright: ignore[reportArgumentType]
)

# https://docs.djangoproject.com/en/dev/ref/settings/#test-runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"

# GITLAB
# ------------------------------------------------------------------------------
if (gitlab_test_host := env.str("GITLAB_TEST_HOST_URL", default=None)) is not None:  # type: ignore[arg-type]
    GITLAB_HOST_URL = gitlab_test_host
GITLAB_HTTP_PROTOCOL = (
    "http" if str(GITLAB_HOST_URL) in {"localhost:9080", "gitlab:9080"} else "https"
)

# AWS S3 CONFIGURATION
# ------------------------------------------------------------------------------
s3_endpoint_url = env.str("AWS_S3_TEST_ENDPOINT_URL", default="") or env.str(
    "AWS_S3_ENDPOINT_URL", default=""
)
if s3_endpoint_url:
    AWS_S3_ENDPOINT_URL: str = s3_endpoint_url  # pyright: ignore[reportAssignmentType]
    AWS_S3_BROWSER_ENDPOINT_URL = (
        env.str(
            "AWS_S3_TEST_BROWSER_ENDPOINT_URL",
            default="",
        )
        or env.str("AWS_S3_BROWSER_ENDPOINT_URL", default="")
        or None
    )
    AWS_S3_USE_SSL = False
    AWS_S3_VERIFY = False
    AWS_S3_ADDRESSING_STYLE = "path"
    # Keep test presigned URLs deterministic across S3-compatible backends even
    # though current boto3/django-storages releases default to Signature V4.
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    custom_domain_endpoint = AWS_S3_BROWSER_ENDPOINT_URL or AWS_S3_ENDPOINT_URL
    custom_domain_host = (
        custom_domain_endpoint.removeprefix("http://")
        .removeprefix("https://")
        .rstrip("/")
    )
    AWS_S3_CUSTOM_DOMAIN = f"{custom_domain_host}/{AWS_STORAGE_BUCKET_NAME}"
    AWS_QUERYSTRING_AUTH = True

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
VITE_ALLOW_MISSING_MANIFEST = True

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "http://media.testserver/"

# django-extensions
# ------------------------------------------------------------------------------
# https://django-extensions.readthedocs.io/en/latest/installation_instructions.html#configuration
INSTALLED_APPS += ["django_extensions"]

# Your stuff...
# ------------------------------------------------------------------------------
