from time import time

from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def maybe_debug_version() -> str:
    """
    Returns '?v=<timestamp>' when DEBUG=True, else empty string.
    """
    if settings.DEBUG:
        return f"?v={int(time())}"
    return ""
