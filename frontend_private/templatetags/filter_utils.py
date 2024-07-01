import datetime
import math
import time

import pytz
import timeago
from django import template
from django.conf import settings
from django.utils import timezone

register = template.Library()


@register.filter(name="time_struct_since")
def time_struct_since(time_struct: time.struct_time):
    dt = datetime.datetime.fromtimestamp(
        time.mktime(time_struct), tz=pytz.timezone(settings.TIME_ZONE)
    )
    dt_now = timezone.now()
    return timeago.format(dt, dt_now)


@register.filter(name="time_struct_format")
def time_struct_format(time_struct: time.struct_time):
    dt = datetime.datetime.fromtimestamp(time.mktime(time_struct))  # noqa: DTZ006

    source_tz = pytz.timezone("Etc/GMT-1")
    dt = source_tz.localize(dt)

    timezone = pytz.timezone("US/Eastern")
    dt = dt.astimezone(timezone)

    return dt.strftime("%Y/%m/%d %H:%M")


@register.filter(name="format_byte_size")
def format_byte_size(size_bytes):
    if size_bytes == 0:
        return "0 B"

    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")

    i = int(math.floor(math.log(size_bytes, 1000)))
    p = math.pow(1000, i)
    s = round(size_bytes / p, 2)

    return f"{s} {size_name[i]}"
