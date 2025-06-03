from __future__ import annotations

from pathlib import Path
from typing import Any

from django.http import FileResponse
from rest_framework.response import Response

from speleodb.utils.helpers import maybe_sort_data


class DownloadResponseFromBlob(FileResponse):
    def __init__(self, obj: Any, filename: str, attachment: bool = True) -> None:
        super().__init__(
            obj,
            as_attachment=attachment,
            filename=filename,
            content_type="application/octet-stream",
        )


class DownloadResponseFromFile(FileResponse):
    def __init__(
        self, filepath: str | Path, filename: str, attachment: bool = True
    ) -> None:
        if not isinstance(filepath, Path):
            filepath = Path(filepath)

        super().__init__(
            filepath.open(mode="rb"),
            as_attachment=attachment,
            filename=filename,
            content_type="application/octet-stream",
        )


class SortedResponse(Response):
    def __init__(self, data: dict[str, Any], *args: Any, **kwargs: Any) -> None:
        super().__init__(maybe_sort_data(data), *args, **kwargs)


class SuccessResponse(Response):
    pass


class ErrorResponse(Response):
    pass


class NoWrapResponse(Response):
    pass
