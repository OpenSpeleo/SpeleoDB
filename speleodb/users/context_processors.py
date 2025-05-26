from typing import Any

from django.conf import settings
from django.http import HttpRequest


def allauth_settings(request: HttpRequest) -> dict[str, Any]:
    """Expose some settings from django-allauth in templates."""
    return {
        "ACCOUNT_ALLOW_REGISTRATION": settings.ACCOUNT_ALLOW_REGISTRATION,
    }
