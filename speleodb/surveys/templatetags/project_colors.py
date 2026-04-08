# -*- coding: utf-8 -*-

from __future__ import annotations

from django import template

from speleodb.common.enums import ColorPalette

register = template.Library()


@register.simple_tag
def get_project_color_palette() -> tuple[str, ...]:
    """Return the shared project color palette for preset swatches."""
    return ColorPalette.COLORS


@register.filter
def country_flag(code: str | None) -> str:
    """Convert an ISO alpha-2 country code to its flag emoji."""
    if not code or len(str(code)) != 2:  # noqa: PLR2004
        return ""
    upper = str(code).upper()
    if not upper.isalpha():
        return ""
    return chr(ord(upper[0]) - 0x41 + 0x1F1E6) + chr(ord(upper[1]) - 0x41 + 0x1F1E6)
