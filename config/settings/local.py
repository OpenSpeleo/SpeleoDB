# -*- coding: utf-8 -*-

from __future__ import annotations

from .base import *  # noqa: F403
from .base import AWS_STORAGE_BUCKET_NAME
from .base import INSTALLED_APPS
from .base import LOGGING
from .base import MIDDLEWARE
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env("DJANGO_SECRET_KEY")
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ["*"]

# GITLAB
# ------------------------------------------------------------------------------
GITLAB_HTTP_PROTOCOL = "http"

# AWS S3 CONFIGURATION
# ------------------------------------------------------------------------------
if (s3_endpoint_url := env.str("AWS_S3_ENDPOINT_URL", default=None)) is not None:  # pyright: ignore[reportArgumentType]
    AWS_S3_ENDPOINT_URL: str = s3_endpoint_url  # pyright: ignore[reportAssignmentType]
    AWS_S3_USE_SSL = False
    AWS_S3_VERIFY = False
    AWS_S3_ADDRESSING_STYLE = "path"
    AWS_S3_CUSTOM_DOMAIN = (
        f"{AWS_S3_ENDPOINT_URL.replace('http://', '')}/{AWS_STORAGE_BUCKET_NAME}"
    )


# LOGGING
# ------------------------------------------------------------------------------

LOGGING["loggers"] = {
    "django": {
        "handlers": ["console"],
        "level": "INFO",
        "propagate": False,
    },
    "werkzeug": {
        "handlers": ["console"],
        "level": "DEBUG",
        "propagate": False,
    },
    # You can also add specific loggers for your apps here
}

# CACHES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "",
    },
}

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.filebased.EmailBackend",  # pyright: ignore[reportArgumentType]
)
EMAIL_FILE_PATH = "./.workdir/emails"

# django-debug-toolbar
# ------------------------------------------------------------------------------
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#prerequisites
INSTALLED_APPS += ["debug_toolbar"]
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#middleware
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
# https://django-debug-toolbar.readthedocs.io/en/latest/configuration.html#debug-toolbar-config
DEBUG_TOOLBAR_CONFIG = {
    "DISABLE_PANELS": [
        "debug_toolbar.panels.redirects.RedirectsPanel",
        "debug_toolbar.panels.profiling.ProfilingPanel",
    ],
    "SHOW_TEMPLATE_CONTEXT": True,
    "SHOW_TOOLBAR_CALLBACK": "speleodb.debug_toolbar.show_toolbar",
}


# django-silk
# ------------------------------------------------------------------------------
INSTALLED_APPS += ["silk"]
MIDDLEWARE += ["silk.middleware.SilkyMiddleware"]

__ENABLE_PROFILING__ = False

# Enable Silk analysis of SQL queries
SILKY_ANALYZE_QUERIES = __ENABLE_PROFILING__

# Enable Silk's internal profiling
SILKY_PYTHON_PROFILER = __ENABLE_PROFILING__

# Record every request (not just decorated ones)
SILKY_INTERCEPT_FUNC = lambda request: __ENABLE_PROFILING__  # noqa: E731

# Optional: store SQL queries and response content
# percentage of requests to profile (100 = all)
SILKY_INTERCEPT_PERCENT = 100 if __ENABLE_PROFILING__ else 0
SILKY_META = __ENABLE_PROFILING__  # optional, include meta info

# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#internal-ips
INTERNAL_IPS = ["127.0.0.1", "10.0.2.2"]
if env.bool("USE_DOCKER", default=False):  # pyright: ignore[reportArgumentType]
    import socket

    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += [".".join([*ip.split(".")[:-1], "1"]) for ip in ips]

# django-extensions
# ------------------------------------------------------------------------------
# https://django-extensions.readthedocs.io/en/latest/installation_instructions.html#configuration
INSTALLED_APPS += ["django_extensions"]

# Celery
# ------------------------------------------------------------------------------

# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-eager-propagates
CELERY_TASK_EAGER_PROPAGATES = True
# Your stuff...
# ------------------------------------------------------------------------------

# django-allauth
# ------------------------------------------------------------------------------
ACCOUNT_ALLOW_REGISTRATION = True
