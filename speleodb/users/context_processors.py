from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings

if TYPE_CHECKING:
    from django.http import HttpRequest


def allauth_settings(request: HttpRequest) -> dict[str, Any]:
    """Expose some settings from django-allauth in templates."""
    return {
        "ACCOUNT_ALLOW_REGISTRATION": settings.ACCOUNT_ALLOW_REGISTRATION,
    }
