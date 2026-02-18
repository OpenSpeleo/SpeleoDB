# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any
from typing import TypedDict
from typing import TypeVar

import requests
from django.conf import settings
from django.core.cache import cache
from django.http import Http404
from django.http.response import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from requests.exceptions import RequestException

from frontend_public.models import BoardMember
from frontend_public.models import ExplorerMember
from frontend_public.models import ScientificMember
from frontend_public.models import TechnicalMember
from speleodb.gis.models import GISView

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest
    from django.http.response import HttpResponseRedirectBase

RT = TypeVar("RT")

logger = logging.getLogger(__name__)

PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=org.speleodb.app"
APP_STORE_URL = "https://apps.apple.com/us/app/speleodb/id6759017618"
COMPASS_SIDECAR_LATEST_JSON_URL = (
    "https://github.com/OpenSpeleo/"
    "speleodb_compass_sidecar/"
    "releases/latest/download/latest.json"
)
COMPASS_SIDECAR_RELEASES_URL = (
    "https://github.com/OpenSpeleo/speleodb_compass_sidecar/releases"
)
COMPASS_SIDECAR_RELEASE_INFO_CACHE_KEY = "frontend_public:compass_sidecar:release_info"
COMPASS_SIDECAR_RELEASE_CACHE_TIMEOUT_SECONDS = 60 * 60  # 1 hour
COMPASS_SIDECAR_FETCH_TIMEOUT_SECONDS = 5.0


class LatestReleaseError(RuntimeError):
    """Raised when the Compass Sidecar Windows URL cannot be resolved."""


class CompassSidecarReleaseInfo(TypedDict):
    windows_url: str
    version: str
    pub_date: str | None


def get_mobile_store_links() -> dict[str, str]:
    return {
        "play_store_url": PLAY_STORE_URL,
        "app_store_url": APP_STORE_URL,
    }


def get_compass_sidecar_release_info(
    *,
    latest_json_url: str = COMPASS_SIDECAR_LATEST_JSON_URL,
    cache_key: str = COMPASS_SIDECAR_RELEASE_INFO_CACHE_KEY,
    cache_timeout: int = COMPASS_SIDECAR_RELEASE_CACHE_TIMEOUT_SECONDS,
    fetch_timeout: float = COMPASS_SIDECAR_FETCH_TIMEOUT_SECONDS,
    releases_fallback_url: str = COMPASS_SIDECAR_RELEASES_URL,
) -> CompassSidecarReleaseInfo:
    fallback_payload: CompassSidecarReleaseInfo = {
        "windows_url": releases_fallback_url,
        "version": "latest",
        "pub_date": None,
    }

    cached_payload = cache.get(cache_key)

    if isinstance(cached_payload, dict):
        cached_windows_url = cached_payload.get("windows_url")
        cached_version = cached_payload.get("version")
        cached_pub_date = cached_payload.get("pub_date")
        if (
            isinstance(cached_windows_url, str)
            and cached_windows_url
            and isinstance(cached_version, str)
            and cached_version
            and (cached_pub_date is None or isinstance(cached_pub_date, str))
        ):
            return {
                "windows_url": cached_windows_url,
                "version": cached_version,
                "pub_date": cached_pub_date,
            }

    try:
        response = requests.api.get(  # type: ignore[no-untyped-call]
            latest_json_url,
            timeout=fetch_timeout,
        )
        response.raise_for_status()

        data = response.json()
        if not isinstance(data, dict):
            raise LatestReleaseError("Invalid latest.json payload format")  # noqa: TRY301

        platforms = data.get("platforms")
        if not isinstance(platforms, dict):
            raise LatestReleaseError("Missing platforms object in latest.json")  # noqa: TRY301

        msi_payload = platforms.get("windows-x86_64-msi")
        if not isinstance(msi_payload, dict):
            raise LatestReleaseError("windows-x86_64-msi not found in latest.json")  # noqa: TRY301

        msi_url = msi_payload.get("url")
        if not isinstance(msi_url, str) or not msi_url:
            raise LatestReleaseError("Invalid windows MSI URL in latest.json")  # noqa: TRY301

        version = data.get("version")
        if not isinstance(version, str) or not version:
            raise LatestReleaseError("Invalid version value in latest.json")  # noqa: TRY301

        pub_date = data.get("pub_date")
        if not isinstance(pub_date, str) or not pub_date:
            pub_date = None

        payload: CompassSidecarReleaseInfo = {
            "windows_url": msi_url,
            "version": version,
            "pub_date": pub_date,
        }

        cache.set(
            cache_key,
            payload,
            timeout=cache_timeout,
        )
        return payload
    except (RequestException, ValueError, LatestReleaseError) as exc:
        logger.warning(
            "Failed to resolve Compass Sidecar release info: %s",
            exc,
        )
        cache.set(
            cache_key,
            fallback_payload,
            timeout=cache_timeout,
        )
        return fallback_payload


def redirect_authenticated_user[RT](
    func: Callable[..., RT],
) -> Callable[..., RT | HttpResponseRedirectBase]:
    def wrapper(
        obj: object, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> RT | HttpResponseRedirectBase:
        if request.user.is_authenticated:
            return redirect("private:user_dashboard")

        return func(obj, request, *args, **kwargs)

    return wrapper


@require_GET
def robots_txt(request: HttpRequest) -> HttpResponse:
    return HttpResponse(
        """\
User-Agent: *
Disallow: /account/
Disallow: /login/
Disallow: /private/
Disallow: /signup/
""",
        content_type="text/plain",
    )


class LoginView(View):
    template_name = "auth/login.html"

    @redirect_authenticated_user
    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            LoginView.template_name,
        )


class PasswordResetFromKeyView(View):
    template_name = "auth/password_reset_from_key.html"

    @redirect_authenticated_user
    def get(self, request: HttpRequest, uidb36: str, key: str) -> HttpResponse:
        return render(
            request,
            PasswordResetFromKeyView.template_name,
            {
                "uidb36": uidb36,
                "key": key,
            },
        )


class PasswordResetView(View):
    template_name = "auth/password_reset.html"

    @redirect_authenticated_user
    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            PasswordResetView.template_name,
        )


class SignUpView(View):
    template_names = {
        True: "auth/signup.html",
        False: "auth/signup_closed.html",
    }

    @redirect_authenticated_user
    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            SignUpView.template_names[settings.ACCOUNT_ALLOW_REGISTRATION],
        )


class HomePageView(TemplateView):
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(get_mobile_store_links())
        return context


class MobileDownloadPageView(TemplateView):
    template_name = "pages/download.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(get_mobile_store_links())
        release_info = get_compass_sidecar_release_info()
        context["compass_sidecar_windows_url"] = release_info["windows_url"]
        context["compass_sidecar_version"] = release_info["version"]
        context["compass_sidecar_pub_date"] = release_info["pub_date"]
        context["compass_sidecar_releases_url"] = COMPASS_SIDECAR_RELEASES_URL
        return context


class PeoplePageView(TemplateView):
    """View for displaying all people involved in the organization."""

    template_name = "pages/people.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Add people data to context."""
        context = super().get_context_data(**kwargs)

        # Fetch all people, already ordered by order then name
        context["board_members"] = BoardMember.objects.all()
        context["technical_members"] = TechnicalMember.objects.all()
        context["explorer_members"] = ExplorerMember.objects.all()
        context["scientific_members"] = ScientificMember.objects.all()

        return context


class PublicGISViewMapViewer(TemplateView):
    """
    Public map viewer for GIS Views - no authentication required.

    Displays a read-only map with only GeoJSON survey data from the
    specified GIS View. All management features (stations, landmarks,
    context menus, etc.) are hidden.
    """

    template_name = "pages/gis_view_map.html"

    def get(
        self,
        request: HttpRequest,
        gis_token: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        # Validate that the GIS View exists
        try:
            gis_view = GISView.objects.get(gis_token=gis_token)
        except GISView.DoesNotExist as e:
            raise Http404("GIS View not found") from e

        context = self.get_context_data(**kwargs)
        context.update(
            {
                "mapbox_api_token": settings.MAPBOX_API_TOKEN,
                "view_mode": "public",  # Key flag for template conditionals
                "gis_view": gis_view,
                "gis_token": gis_token,
            }
        )
        return self.render_to_response(context)
