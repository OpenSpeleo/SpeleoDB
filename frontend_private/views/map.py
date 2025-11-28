# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings

from frontend_private.views.base import AuthenticatedTemplateView

if TYPE_CHECKING:
    from django.http import HttpResponse
    from django.http.response import HttpResponseRedirectBase

    from speleodb.utils.requests import AuthenticatedHttpRequest


class MapViewerView(AuthenticatedTemplateView):
    template_name = "pages/map_viewer.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        data = {
            "mapbox_api_token": settings.MAPBOX_API_TOKEN,
        }
        return super().get(request, *args, **data, **kwargs)
