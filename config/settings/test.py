# -*- coding: utf-8 -*-

"""
Test Django settings for SpeleoDB project.

- Use fast password hashing
- Use isolated PostgreSQL databases for the complete backend suite
- Use temporary directory for media files
- Disable migrations where possible
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from speleodb.testing.gitlab_audit import LEDGER_ENV
from speleodb.testing.gitlab_audit import install_guard

if LEDGER_ENV in os.environ:
    install_guard()


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

# Exercise the supported impersonation routes in the default suite, including
# CI where DEBUG is false. Restore the environment after importing base settings
# so production-settings subprocess probes do not inherit this test-only choice.
_hijack_environment: dict[str, str | None] = {
    name: os.environ.get(name) for name in ("ALLOW_USER_DEBUG", "DJANGO_HIJACK_URL")
}
os.environ["ALLOW_USER_DEBUG"] = "true"
os.environ["DJANGO_HIJACK_URL"] = "debug_mode/"


try:
    from config.settings.base import *  # noqa: F403
    from config.settings.base import AWS_STORAGE_BUCKET_NAME
    from config.settings.base import INSTALLED_APPS
    from config.settings.base import TEMPLATES
    from config.settings.base import env
finally:
    for _name, _value in _hijack_environment.items():
        if _value is None:
            os.environ.pop(_name, None)
        else:
            os.environ[_name] = _value

# Test database selection belongs to the test environment, independently of the
# development container's POSTGRES_* configuration.
DATABASES = {"default": env.db("DATABASE_URL")}
# A real Celery child process must connect to pytest's already-created PostgreSQL
# database, without having the private test dotenv replace that exact address.
if test_database_url := env.str("TEST_DATABASE_URL", default=""):
    DATABASES = {"default": env.db_url_config(test_database_url)}
# Replacing the connection mapping above must preserve production transactions.
DATABASES["default"]["ATOMIC_REQUESTS"] = True
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured(
        "The complete backend suite requires PostgreSQL. Configure DATABASE_URL "
        "in .envs/test.env or supply an explicit TEST_DATABASE_URL. "
        "Test settings never replace that choice with the development database."
    )
# Tests own their schema. A developer's template1 can contain custom objects or
# stale collation metadata after a glibc/musl container-image change.
DATABASES["default"]["TEST"] = {"TEMPLATE": "template0"}

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
# https://docs.djangoproject.com/en/dev/ref/settings/#mailers
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}

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

# The integration fixtures select this dedicated service for their own workers.
# Ordinary tests keep an in-process transport so their messages cannot leak into
# a later live-worker test or reach development workers.
TEST_CELERY_BROKER_URL: str = env.str(
    "TEST_CELERY_BROKER_URL", default="redis://localhost:6381/0"
)
CELERY_BROKER_URL = "memory://"
# Celery reads this environment key before its app configuration. Override the
# inherited development broker so test settings actually isolate every publisher.
os.environ["CELERY_BROKER_URL"] = CELERY_BROKER_URL
EXPORTS_PUBLIC_BASE_URL = "http://testserver"
