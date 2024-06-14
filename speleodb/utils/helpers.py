#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import OrderedDict

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from speleodb.utils.exceptions import NotAuthorizedError


def get_timestamp():
    return timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")


def maybe_sort_data(data):
    if isinstance(data, (dict, OrderedDict)):
        return OrderedDict(
            {key: maybe_sort_data(val) for key, val in sorted(data.items())}
        )

    if isinstance(data, (tuple, list)):
        return [maybe_sort_data(_data) for _data in data]

    return data


def str2bool(v):
    if isinstance(v, bool):
        return v
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
