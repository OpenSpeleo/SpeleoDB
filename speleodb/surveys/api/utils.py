from collections import OrderedDict

from rest_framework.response import Response


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
