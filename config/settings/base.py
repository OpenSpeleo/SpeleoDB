# -*- coding: utf-8 -*-
"""Base settings to build other settings files upon."""

# ruff: noqa: E501

from __future__ import annotations

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent

# APPS_DIR = BASE_DIR / "speleodb"

env = environ.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=True)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(BASE_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)
DEBUG_GITLAB = env.bool("DJANGO_DEBUG_GITLAB", False)

# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "US/Eastern"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True

# Git Project Saving
# ------------------------------------------------------------------------------

# Space where projects are being saved
DJANGO_GIT_PROJECTS_DIR = env(
    "DJANGO_GIT_PROJECT_DIR", default=BASE_DIR / ".workdir/git_projects"
)
DJANGO_TMP_DL_DIR = env("DJANGO_TMP_DL_DIR", default=BASE_DIR / ".workdir/tmp_dl_dir")

DJANGO_GIT_COMMITTER_NAME = env("GIT_COMMITTER_NAME", default="SpeleoDB")
DJANGO_GIT_COMMITTER_EMAIL = env("GIT_COMMITTER_EMAIL", default="contact@speleodb.org")
DJANGO_GIT_FIRST_COMMIT_MESSAGE = env(
    "GIT_FIRST_COMMIT_MESSAGE", default="[Automated] Project Creation"
)

DJANGO_GIT_RETRY_ATTEMPTS = 5
DJANGO_GIT_BRANCH_NAME = "master"

# File Upload Limits
# ------------------------------------------------------------------------------
DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT = 5  # File size limit per individual file
DJANGO_UPLOAD_TOTAL_FILESIZE_MB_LIMIT = 50  # File size limit for an entire commit
DJANGO_UPLOAD_TOTAL_FILES_LIMIT = 20  # Maxmimum number of files simultaneously uploaded

# The maximum size in bytes that a request body
# ------------------------------------------------------------------------------
DATA_UPLOAD_MAX_MEMORY_SIZE = 5_242_880  # 5 MB in bytes

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
    # DATABASES = {
    #     "default": {
    #         "ENGINE": "django.db.backends.postgresql",
    #         "HOST": env("POSTGRES_HOST"),
    #         "PORT": env("POSTGRES_PORT"),
    #         "NAME": env("POSTGRES_DB"),
    #         "USER": env("POSTGRES_USER"),
    #         "PASSWORD": env("POSTGRES_PASSWORD"),
    #     }
    # }
DATABASES["default"]["ATOMIC_REQUESTS"] = True
# https://docs.djangoproject.com/en/stable/ref/settings/#std:setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "config.urls"
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # "django.contrib.humanize", # Handy template tags
    "django.contrib.admin",
    "django.forms",
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
    "allauth.headless",
    "django_celery_beat",
    # DRF
    "corsheaders",
    "drf_spectacular",
    "rest_framework",
    "rest_framework.authtoken",
    # ============ CUSTOM ADDITIONS ============ #
    # https://github.com/SmileyChris/django-countries
    # A Django application that provides country choices for use with forms,
    # flag icons static files, and a country field for models.
    "django_countries",
    # https://github.com/lincolnloop/django-dynamic-raw-id
    # A raw_id_fields widget replacement that handles display of an object's
    # string value on change and can be overridden via a template.
    "dynamic_raw_id",
    # https://github.com/enderlabs/django-cryptographic-fields
    # A set of fields that wrap standard Django fields with encryption provided
    # by the python cryptography library.
    "encrypted_model_fields",
    # https://github.com/django-hijack/django-hijack
    # With Django Hijack, admins can log in and work on behalf of other users
    # without having to know their credentials.
    # Author's NOTE: Unfortunately this mechanism is necessary for debugging any
    #                user's issue - being able to see what they see. This needs
    #                to be used as an absolute last last resort.
    "hijack",
    "hijack.contrib.admin",
]

if DEBUG:
    THIRD_PARTY_APPS += [
        "schema_viewer",
        "silk",
    ]

LOCAL_APPS = [
    # API Apps
    "speleodb.api.v1",
    # Git Apps
    "speleodb.git_proxy",
    # Object Apps
    "speleodb.common",
    "speleodb.surveys",
    "speleodb.users",
    # HTML Apps
    "frontend_errors",
    "frontend_private",
    "frontend_public",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
MIGRATION_MODULES = {"sites": "speleodb.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
AUTH_USER_MODEL = "users.User"

# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = True

# https://docs.allauth.org/en/latest/headless/installation.html
HEADLESS_ONLY = True
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": "/account/confirm-email/{key}",
    "account_reset_password": "/account/password/reset",
    "account_reset_password_from_key": "/account/password/reset/{key}",
    "account_signup": "/signup",
}

# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "private:user_dashboard"
# https://docs.djangoproject.com/en/dev/ref/settings/#logout-redirect-url
LOGOUT_REDIRECT_URL = "home"

# https://docs.djangoproject.com/en/dev/ref/settings/#login-url
LOGIN_URL = "account_login"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    # https://docs.djangoproject.com/en/dev/topics/auth/passwords/#using-argon2-with-django
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# DJANGO COUNTRIES
# ------------------------------------------------------------------------------
# https://github.com/SmileyChris/django-countries#show-certain-countries-first
COUNTRIES_FIRST = ["US", "MX", "FR"]

# https://github.com/SmileyChris/django-countries/blob/main/django_countries/data.py
COUNTRIES_OVERRIDE = {
    "AB": "Scotland",
    "BO": "Bolivia",
    "BQ": "Bonaire",
    "CD": "Congo",
    "FM": "Micronesia",
    "GB": "Great Britain",
    "GS": "South Georgia",
    "IR": "Iran",
    "KP": "North Korea",
    "KR": "South Korea",
    "LA": "Laos",
    "MD": "Moldova",
    "MF": "Saint Martin",
    "SH": "Saint Helena",
    "TW": "Taiwan",
    "UM": "US Minor Outlying Islands",
    "US": "USA",
    "VE": "Venezuela",
    "VG": "Virgin Islands (GB)",
    "VI": "Virgin Islands (USA)",
}

# ENCRYPTED FIELDS
# ------------------------------------------------------------------------------
# https://gitlab.com/lansharkconsulting/django/django-encrypted-model-fields/#getting-started
FIELD_ENCRYPTION_KEY = env("DJANGO_FIELD_ENCRYPTION_KEY")

# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "hijack.middleware.HijackUserMiddleware",
    "speleodb.middleware.ViewNameMiddleware",
    "speleodb.middleware.DRFWrapResponseMiddleware",
]

if DEBUG:
    MIDDLEWARE += ["silk.middleware.SilkyMiddleware"]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(BASE_DIR / "staticfiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
# STATICFILES_DIRS = [str(APPS_DIR / "static")]
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = str(BASE_DIR / "mediafiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "/media/"

# AWS S3 CONFIGURATION
# ------------------------------------------------------------------------------
USE_S3 = env.bool("USE_S3", default=False)

if USE_S3:
    # AWS Settings
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="us-east-1")
    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"

    # S3 Storage Settings
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
    }
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = "private"

    # Static and Media Storage
    DEFAULT_FILE_STORAGE = "speleodb.utils.storages.MediaStorage"

    # Update media URL to use S3
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"
else:
    # Local file storage (default)
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

    # Use custom local media root if specified
    LOCAL_MEDIA_ROOT = env("LOCAL_MEDIA_ROOT", default=None)
    if LOCAL_MEDIA_ROOT:
        MEDIA_ROOT = LOCAL_MEDIA_ROOT
        Path(MEDIA_ROOT).mkdir(parents=True, exist_ok=True)

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#dirs
        # "DIRS": [str(APPS_DIR / "templates")],
        # https://docs.djangoproject.com/en/dev/ref/settings/#app-dirs
        "APP_DIRS": True,
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "speleodb.users.context_processors.allauth_settings",
            ],
        },
    },
]

# https://docs.djangoproject.com/en/dev/ref/settings/#form-renderer
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
# FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-timeout
EMAIL_TIMEOUT = 5

# DJANGO-HIJACK
# ------------------------------------------------------------------------------
# Django Hijack URL.
HIJACK_URL = "debug_mode/"
# Hide notification if `None`.
HIJACK_INSERT_BEFORE: str | None = None

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = "admin/"

# https://docs.djangoproject.com/en/dev/ref/settings/#admins
# A list of all the people who get code error notifications.
# When DEBUG=False and AdminEmailHandler is configured in LOGGING
# (done by default), Django emails these people the details of
# exceptions raised in the request/response cycle.
# NOTE: Please do not change this email - It helps us to get crash reports
ADMINS = [("""Jonathan Dekhtiar""", "jonathan@dekhtiar.com")]

# https://docs.djangoproject.com/en/dev/ref/settings/#managers
# A list in the same format as ADMINS that specifies who should get broken
# link notifications when BrokenLinkEmailsMiddleware is enabled.
# NOTE: Please do not change this email - It helps us to get crash reports
MANAGERS = ADMINS

# https://cookiecutter-django.readthedocs.io/en/latest/settings.html#other-environment-settings
# Force the `admin` sign in process to go through the `django-allauth` workflow
DJANGO_ADMIN_FORCE_ALLAUTH = env.bool("DJANGO_ADMIN_FORCE_ALLAUTH", default=False)

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

# Celery
# ------------------------------------------------------------------------------
if USE_TZ:
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-timezone
    CELERY_TIMEZONE = TIME_ZONE
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-broker_url
CELERY_BROKER_URL = ""  # env("CELERY_BROKER_URL")
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_backend
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-extended
CELERY_RESULT_EXTENDED = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-always-retry
# https://github.com/celery/celery/pull/6122
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-max-retries
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-accept_content
CELERY_ACCEPT_CONTENT = ["json"]
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-task_serializer
CELERY_TASK_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_serializer
CELERY_RESULT_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_TIME_LIMIT = 5 * 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-soft-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_SOFT_TIME_LIMIT = 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#beat-scheduler
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-send-task-events
CELERY_WORKER_SEND_TASK_EVENTS = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-task_send_sent_event
CELERY_TASK_SEND_SENT_EVENT = True
# django-allauth
# ------------------------------------------------------------------------------
ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", True)
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_LOGIN_METHODS = {"email"}
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_CHANGE_EMAIL = True
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_LOGOUT_ON_GET = True
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_SIGNUP_FIELDS = ["name*", "country*", "email*", "password1*", "password2*"]
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_USER_MODEL_USERNAME_FIELD: str | None = None
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_ADAPTER = "speleodb.users.adapters.AccountAdapter"
# https://docs.allauth.org/en/latest/account/forms.html
# ACCOUNT_FORMS = {"signup": "speleodb.users.forms.SignupForm"}
ACCOUNT_SIGNUP_FORM_CLASS = "speleodb.users.forms.SignupForm"
# django-compressor
# ------------------------------------------------------------------------------
# https://django-compressor.readthedocs.io/en/latest/quickstart/#installation
INSTALLED_APPS += ["compressor"]
STATICFILES_FINDERS += ["compressor.finders.CompressorFinder"]
# django-rest-framework
# -------------------------------------------------------------------------------
# django-rest-framework - https://www.django-rest-framework.org/api-guide/settings/
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
        "speleodb.api.v1.authentication.BearerAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

if env.bool("DJANGO_DEBUG_DRF_AUTH", default=False):
    # Needs to be insert as the very first Auth Processor to ensure it being processed.
    REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = [
        "speleodb.api.v1.authentication.DebugHeaderAuthentication",
        *REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"],
    ]

# django-cors-headers - https://github.com/adamchainz/django-cors-headers#setup
CORS_URLS_REGEX = r"^/api/.*$"

# By Default swagger ui is available only to admin user(s). You can change permission classes to change that
# See more configuration options at https://drf-spectacular.readthedocs.io/en/latest/settings.html#settings
SPECTACULAR_SETTINGS = {
    "TITLE": "SpeleoDB API",
    "DESCRIPTION": "Documentation of API endpoints of SpeleoDB",
    "VERSION": "1.0.0",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    "SCHEMA_PATH_PREFIX": "/api/",
}

# Custom Settings
# ------------------------------------------------------------------------------
