# -*- coding: utf-8 -*-

"""
Test Django settings for SpeleoDB project.

- Use fast password hashing
- Use in-memory SQLite for tests
- Use temporary directory for media files
- Disable migrations where possible
"""

from __future__ import annotations

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

# Have to overwrite because of `USE_DOCKER` in base.py
DATABASES = {"default": env.db("DATABASE_URL")}

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

# Your stuff...
# ------------------------------------------------------------------------------
