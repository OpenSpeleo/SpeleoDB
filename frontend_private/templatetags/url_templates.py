import uuid
from typing import Any

from django import template
from django.urls import reverse

register = template.Library()


def _url_template(view_name: str, param_name: str, param_plh: Any) -> str:
    """
    Returns the URL pattern of a view, with a placeholder for the param.

    Usage:
        {% url_pattern 'api:v1:project-detail' 'id' %}
    Returns:
        /api/projects/{id}/
    """
    placeholder = f"__{param_name}__"

    # Get the URL pattern (if view exists without params)
    url = reverse(view_name, kwargs={param_name: param_plh})
    # Replace dummy with placeholder
    return url.replace(param_plh, placeholder)


@register.simple_tag
def url_int_template(view_name: str, param_name: str) -> str:
    # Try reversing with a valid dummy int
    return _url_template(view_name, param_name, str(9999999))


@register.simple_tag
def url_str_template(view_name: str, param_name: str) -> str:
    # Try reversing with a valid dummy int
    return _url_template(view_name, param_name, "__magic__")


@register.simple_tag
def url_uuid_template(view_name: str, param_name: str) -> str:
    # Try reversing with a valid dummy int
    return _url_template(view_name, param_name, str(uuid.UUID(int=0)))
