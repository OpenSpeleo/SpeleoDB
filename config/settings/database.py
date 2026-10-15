"""Database configuration without importing application settings."""

from __future__ import annotations

from config.settings.environment import env

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases
if env.bool("USE_DOCKER", default=False):
    # DATABASES = {"default": env.db("DATABASE_URL")}
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": env("POSTGRES_HOST"),
            "PORT": env("POSTGRES_PORT"),
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER"),
            "PASSWORD": env("POSTGRES_PASSWORD"),
        }
    }
else:
    DATABASES = {"default": env.db("DATABASE_URL")}

DATABASES["default"]["ATOMIC_REQUESTS"] = True
