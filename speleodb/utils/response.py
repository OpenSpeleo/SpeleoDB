""":py:class:`django.http.HttpResponse` subclasses."""

from pathlib import Path

from django.http import FileResponse
from rest_framework.response import Response

from speleodb.utils.utils import maybe_sort_data


class DownloadTMLResponseFromFile(FileResponse):
    def __init__(self, filepath, attachment=True):
        filepath = Path(filepath)
        super().__init__(
            filepath.open(mode="rb"),
            as_attachment=attachment,
            filename=filepath.name,
            content_type="application/zip",
        )


class SortedResponse(Response):
    def __init__(self, data, *args, **kwargs):
        data = maybe_sort_data(data)
        for key, val in data.items():
            data[key] = maybe_sort_data(val)
        super().__init__(data, *args, **kwargs)
