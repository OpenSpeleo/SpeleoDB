#!/usr/bin/env python
# -*- coding: utf-8 -*-
from collections import OrderedDict
from typing import Any
from typing import TypeVar

from django.utils import timezone

T = TypeVar("T")


def get_timestamp() -> str:
    return timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")


def maybe_sort_data(data: T) -> OrderedDict[str, Any] | list[Any] | T:
    match data:
        case dict():
            return OrderedDict(
                {key: maybe_sort_data(val) for key, val in sorted(data.items())}
            )

        case tuple() | list():
            return [maybe_sort_data(_data) for _data in data]

    return data


def str2bool(v: str) -> bool:
    if not isinstance(v, str):
        raise TypeError(f"Expected `str`, received: `{type(v)}`")
    return v.lower() in [
        "true",
        "1",
        "t",
        "y",
        "yes",
        "yeah",
        "yup",
        "certainly",
        "uh-huh",
    ]
