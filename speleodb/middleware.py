# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.http import FileResponse
from django.http import HttpRequest
from django.http import HttpResponse
from django.urls import resolve
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.renderers import JSONRenderer
from rest_framework.settings import api_settings

from speleodb.utils.exceptions import NotAuthorizedError
from speleodb.utils.helpers import get_timestamp
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import NoWrapResponse
from speleodb.utils.response import SortedResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence

    from rest_framework.request import Request
    from rest_framework.response import Response


class ViewNameMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        url_name = resolve(request.path).url_name
        request.url_name = url_name  # type: ignore[attr-defined]

        return self.get_response(request)


class DRFWrapResponseMiddleware:
    renderers: Sequence[str]

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        # One-time configuration and initialization.
        from rest_framework.negotiation import (  # noqa: PLC0415
            DefaultContentNegotiation,
        )

        self.get_response = get_response
        self.renderers = api_settings.DEFAULT_RENDERER_CLASSES
        self.negotiator = DefaultContentNegotiation()

    def select_renderer(self, request: Request) -> Any:
        return self.negotiator.select_renderer(request, self.renderers)  # type: ignore[arg-type]

    def __call__(self, request: Request) -> Response | HttpResponse:  # noqa: PLR0915
        # Skip for non-API calls
        if "/api/" not in request.path:
            return self.get_response(request)

        payload = {}
        http_status = None
        exception = False

        wrapped_response: HttpResponse | None = None
        try:
            wrapped_response = self.get_response(request)

            if wrapped_response.status_code == status.HTTP_304_NOT_MODIFIED:
                return wrapped_response

            if not any(
                request.path.startswith(path) for path in ["/api/v1", "/api/health"]
            ):
                return wrapped_response

            if isinstance(wrapped_response, FileResponse):
                return wrapped_response

            if isinstance(wrapped_response, ErrorResponse):
                payload.update(wrapped_response.data)
                exception = True

            elif isinstance(wrapped_response, NoWrapResponse):
                payload.update(wrapped_response.data)

            elif isinstance(wrapped_response, SuccessResponse):
                payload.update({"data": wrapped_response.data})

            else:
                data = getattr(wrapped_response, "data", None)
                match data:
                    case dict():
                        payload.update(data)
                    case None:
                        pass
                    case _:
                        payload.update({"data": data})
                exception = True

            http_status = wrapped_response.status_code

        except (NotAuthorizedError, PermissionDenied) as e:
            if settings.DEBUG:
                raise

            payload["data"] = {}
            payload["error"] = f"An error occured in the process: {e}"
            http_status = status.HTTP_403_FORBIDDEN
            exception = True

        except Exception as e:  # noqa: BLE001, RUF100
            if settings.DEBUG:
                raise

            payload["data"] = {}
            payload["error"] = f"An error occured in the process: {e}"
            http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            exception = True

        payload["url"] = request.build_absolute_uri()
        payload["timestamp"] = get_timestamp()
        payload["success"] = http_status in range(200, 300)

        response = SortedResponse(payload, status=http_status)
        response.exception = exception

        if wrapped_response is not None:
            try:
                response.accepted_renderer = wrapped_response.accepted_renderer  # type: ignore[attr-defined]
                response.accepted_media_type = wrapped_response.accepted_media_type  # type: ignore[attr-defined]
                response.renderer_context = wrapped_response.renderer_context  # type: ignore[attr-defined]

            except (NameError, AttributeError):
                response.accepted_renderer = JSONRenderer()
                response.accepted_media_type = "application/json"
                response.renderer_context = {}  # type: ignore[attr-defined]
        else:
            response.accepted_renderer = JSONRenderer()
            response.accepted_media_type = "application/json"
            response.renderer_context = {}  # type: ignore[attr-defined]

        response.render()

        return response
