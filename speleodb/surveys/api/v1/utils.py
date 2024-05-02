from collections import OrderedDict

from django.utils import timezone
from rest_framework import exceptions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


def get_timestamp():
    return timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")


def _sort_data(data):
    if isinstance(data, dict):
        return OrderedDict(sorted(data.items()))

    if isinstance(data, (tuple, list)):
        return [_sort_data(_data) for _data in data]

    raise TypeError(f"Unsupported type: `{type(data)}`")


class SortedResponse(Response):
    def __init__(self, data, *args, **kwargs):
        data = _sort_data(data)
        super().__init__(data, *args, **kwargs)


class CustomAPIView(APIView):
    def get(self, request, *args, **kwargs):
        if not hasattr(self, "_get"):
            raise exceptions.MethodNotAllowed(request.method)

        payload = {}
        http_status = status.HTTP_200_OK
        try:
            payload["data"] = self._get(request, *args, **kwargs)

        except Exception as e:  # noqa: BLE001
            payload["success"] = False
            payload["error"] = f"An error occured in the process: {e}"
            http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

        payload["url"] = request.build_absolute_uri()
        payload["timestamp"] = get_timestamp()
        return SortedResponse(payload, status=http_status)
