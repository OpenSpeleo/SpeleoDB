from collections import OrderedDict

from django.utils import timezone
from rest_framework.response import Response


def get_timestamp():
    return timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")


def maybe_sort_data(data):
    if isinstance(data, dict):
        return OrderedDict(sorted(data.items()))

    if isinstance(data, (tuple, list)):
        return [maybe_sort_data(_data) for _data in data]

    return data


class SortedResponse(Response):
    def __init__(self, data, *args, **kwargs):
        data = maybe_sort_data(data)
        for key, val in data.items():
            data[key] = maybe_sort_data(val)
        super().__init__(data, *args, **kwargs)
