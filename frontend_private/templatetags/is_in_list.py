from __future__ import annotations

from typing import Any

from django import template

register = template.Library()


@register.filter(name="is_in_list")
def is_in_list(value: Any, values: str | list[Any]) -> bool:
    if isinstance(values, str):
        values = values.split(",")
    return value in values
