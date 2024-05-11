#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import OrderedDict

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


def wrap_response_with_status(func, request, *args, **kwargs):
    payload = {}
    http_status = status.HTTP_200_OK
    try:
        response = func(request, *args, **kwargs)

        if isinstance(response, Response):
            payload.update(response.data)
            http_status = response.status_code

        elif isinstance(response, (list, tuple, dict)):
            payload["data"] = response

        else:
            payload["data"] = f"Unsupported response type: {type(response)}"
            http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

    except (NotAuthorizedError, PermissionDenied) as e:
        payload["data"] = {}
        payload["error"] = f"An error occured in the process: {e}"
        http_status = status.HTTP_403_FORBIDDEN

    except Exception as e:  # noqa: BLE001
        payload["data"] = {}
        payload["error"] = f"An error occured in the process: {e}"
        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

    payload["url"] = request.build_absolute_uri()
    payload["timestamp"] = get_timestamp()
    payload["success"] = http_status in range(200, 300)

    from speleodb.utils.response import SortedResponse

    return SortedResponse(payload, status=http_status)
