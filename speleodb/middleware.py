# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

import sentry_sdk
from allauth.account import app_settings as account_settings
from allauth.headless.account.views import ManagePhoneView
from allauth.headless.account.views import ResendPhoneVerificationCodeView
from allauth.headless.account.views import VerifyPhoneView
from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.http import FileResponse
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.http import StreamingHttpResponse
from django.http.response import HttpResponseRedirectBase
from django.urls import resolve
from django.utils.cache import add_never_cache_headers
from django.utils.deprecation import MiddlewareMixin
from hijack.middleware import HijackUserMiddleware
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.negotiation import DefaultContentNegotiation
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

logger = logging.getLogger(__name__)


class HeadlessPhoneFeatureMiddleware(MiddlewareMixin):
    """Reject unavailable phone management before unimplemented adapter hooks."""

    def process_view(
        self,
        request: HttpRequest,
        view_func: Callable[..., Any],
        view_args: Sequence[Any],
        view_kwargs: dict[str, Any],
    ) -> HttpResponse | None:
        if (
            getattr(view_func, "view_class", None)
            in {ManagePhoneView, VerifyPhoneView, ResendPhoneVerificationCodeView}
            and (
                request.method == "POST"
                or (
                    request.method in {"GET", "HEAD"}
                    and getattr(view_func, "view_class", None) is ManagePhoneView
                )
            )
            and "phone" not in account_settings.SIGNUP_FIELDS
        ):
            response = JsonResponse(
                {"status": status.HTTP_409_CONFLICT}, status=status.HTTP_409_CONFLICT
            )
            add_never_cache_headers(response)
            return response
        return None


class HeadlessAwareHijackUserMiddleware(HijackUserMiddleware):
    """Keep app session-token authentication independent of browser impersonation.

    django-hijack wraps a copy of the cookie user in a lazy object. Allauth's
    app context changes request.session and resets that lazy object, but the
    hijack closure still points at the original cookie user. Preserve Django's
    session-aware lookup for the two mounted app routes instead.
    """

    def process_request(self, request: HttpRequest) -> None:
        if request.path_info.startswith(("/_allauth/app/", "/api/auth/app/")):
            return
        super().process_request(request)  # type: ignore[no-untyped-call]


class LastLoginUpdateMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        # One-time configuration and initialization.
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Note this middleware only works for Session-based authentication
        # Does not work for Django Token auth: Anonymous until DRF Auth.
        if request.user.is_authenticated:
            update_last_login(None, user=request.user)  # type: ignore[arg-type]

        return self.get_response(request)


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
        self.get_response = get_response
        self.renderers = api_settings.DEFAULT_RENDERER_CLASSES
        self.negotiator = DefaultContentNegotiation()

    def select_renderer(self, request: Request) -> Any:
        return self.negotiator.select_renderer(request, self.renderers)  # type: ignore[arg-type]

    def __call__(self, request: Request) -> Response | HttpResponse:
        # Skip for non-API calls
        if "/api/v1/" not in request.path:
            return self.get_response(request)

        payload = {}
        http_status = None
        exception = False

        wrapped_response: HttpResponse | None = None
        try:
            wrapped_response = self.get_response(request)

            if wrapped_response.status_code == status.HTTP_304_NOT_MODIFIED:
                return wrapped_response

            match wrapped_response:
                case (
                    NoWrapResponse()
                    | FileResponse()
                    | StreamingHttpResponse()
                    | HttpResponseRedirect()
                    | HttpResponseRedirectBase()
                ):
                    return wrapped_response

                case ErrorResponse():
                    payload.update(wrapped_response.data)
                    exception = True

                case SuccessResponse():
                    payload.update({"data": wrapped_response.data})

                case _:
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

            logger.exception("API permission error at %s", request.path)
            payload["error"] = f"An error occured in the process: {e}"
            http_status = status.HTTP_403_FORBIDDEN
            exception = True

        except Exception as e:  # noqa: BLE001, RUF100
            if settings.DEBUG:
                raise

            logger.exception("Unhandled API exception at %s", request.path)
            sentry_sdk.capture_exception(e)
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

            except NameError, AttributeError:
                response.accepted_renderer = JSONRenderer()
                response.accepted_media_type = "application/json"
                response.renderer_context = {}  # type: ignore[attr-defined]
        else:
            response.accepted_renderer = JSONRenderer()
            response.accepted_media_type = "application/json"
            response.renderer_context = {}  # type: ignore[attr-defined]

        response.render()

        return response
