"""Line-breaking opportunities for long references in the PDF typesetter."""

from __future__ import annotations

import re

from django import template

register = template.Library()


@register.filter
def receipt_wrap(value: str, column_width: int = 44) -> str:
    # MuPDF clips unbroken words wider than the page. Insert a line break
    # only within long tokens, preserving every character of the reference.
    return re.sub(rf"(\S{{{column_width}}})(?=\S)", r"\1\n", str(value))
