# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime
import math
from typing import TYPE_CHECKING

import pytz
import timeago
from django import template
from django.conf import settings
from django.utils import timezone

if TYPE_CHECKING:
    import time

register = template.Library()


def datetime_of_struct_time(st: time.struct_time) -> datetime.datetime:
    "Convert a struct_time to datetime maintaining timezone information when present"
    tz = None
    if st.tm_gmtoff is not None:
        tz = datetime.timezone(datetime.timedelta(seconds=st.tm_gmtoff))
    # datetime doesn't like leap seconds so just truncate to 59 seconds
    if st.tm_sec in {60, 61}:
        dt = datetime.datetime(*st[:5], 59, tzinfo=tz)
    dt = datetime.datetime(*st[:6], tzinfo=tz)

    return dt.astimezone(pytz.timezone(settings.TIME_ZONE))


@register.filter(name="time_struct_since")
def time_struct_since(time_struct: time.struct_time) -> str:
    dt = datetime_of_struct_time(time_struct)
    dt_now = timezone.now()
    return timeago.format(dt, dt_now)  # type: ignore[no-any-return,no-untyped-call]


@register.filter(name="time_struct_format")
def time_struct_format(time_struct: time.struct_time) -> str:
    dt = datetime_of_struct_time(time_struct)
    return dt.strftime("%Y/%m/%d %H:%M")


@register.filter(name="format_byte_size")
def format_byte_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"

    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")

    i = math.floor(math.log(size_bytes, 1000))
    p = math.pow(1000, i)
    s = round(size_bytes / p, 2)

    return f"{s} {size_name[i]}"
