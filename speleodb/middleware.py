#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.conf import settings
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


class ViewNameMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        url_name = resolve(request.path).url_name
        request.url_name = url_name

        return self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.


class DRFWrapResponseMiddleware:
    def __init__(self, get_response):
        # One-time configuration and initialization.
        from rest_framework.negotiation import DefaultContentNegotiation

        self.get_response = get_response
        self.renderers = api_settings.DEFAULT_RENDERER_CLASSES
        self.negotiator = DefaultContentNegotiation()

    def select_renderer(self, request):
        return self.negotiator.select_renderer(request, self.renderers)

    def __call__(self, request):
        # Skip for non-API calls
        if "/api/" not in request.path:
            return self.get_response(request)

        payload = {}
        http_status = None
        exception = False

        try:
            wrapped_response = self.get_response(request)

            if isinstance(wrapped_response, ErrorResponse):
                payload.update(wrapped_response.data)
                exception = True

            elif isinstance(wrapped_response, NoWrapResponse):
                payload.update(wrapped_response.data)

            elif isinstance(wrapped_response, SuccessResponse):
                payload.update({"data": wrapped_response.data})

            else:
                try:
                    payload.update(wrapped_response.data)
                    exception = True
                except Exception:  # noqa: BLE001
                    return wrapped_response

            http_status = wrapped_response.status_code

        except (NotAuthorizedError, PermissionDenied) as e:
            if settings.DEBUG:
                raise

            payload["data"] = {}
            payload["error"] = f"An error occured in the process: {e}"
            http_status = status.HTTP_403_FORBIDDEN
            exception = True

        except Exception as e:
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

        try:
            response.accepted_renderer = wrapped_response.accepted_renderer
            response.accepted_media_type = wrapped_response.accepted_media_type
            response.renderer_context = wrapped_response.renderer_context
        except (NameError, AttributeError):
            response.accepted_renderer = JSONRenderer()
            response.accepted_media_type = "application/json"
            response.renderer_context = {}

        response.render()

        return response
