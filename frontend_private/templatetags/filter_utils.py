# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime as dt
import math

import timeago
from django import template
from django.utils import timezone
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def local_date(value: dt.date | None, fallback: str = "") -> str:
    """Expose timestamps and calendar dates to the shared browser formatter."""
    if not value:
        return fallback
    mode = "datetime" if isinstance(value, dt.datetime) else "date"
    iso_value = value.isoformat()
    return format_html(
        '<time datetime="{}" data-local-date="{}">{}</time>',
        iso_value,
        mode,
        iso_value,
    )


@register.filter(name="datetime_since")
def datetime_since(value: dt.datetime) -> str:
    """Format elapsed time without discarding the input's timezone."""
    return timeago.format(value, timezone.now())  # type: ignore[no-any-return,no-untyped-call]


@register.filter(name="format_byte_size")
def format_byte_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"

    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")

    i = math.floor(math.log(size_bytes, 1000))
    p = math.pow(1000, i)
    s = round(size_bytes / p, 2)

    return f"{s} {size_name[i]}"
