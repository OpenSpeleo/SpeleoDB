# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.urls import reverse
from rest_framework.authtoken.models import Token

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.gis.models import GISView

if TYPE_CHECKING:
    from django.http import HttpResponse
    from django.http.response import HttpResponseRedirectBase

    from speleodb.users.models import User
    from speleodb.utils.requests import AuthenticatedHttpRequest


class GISViewListingView(AuthenticatedTemplateView):
    """List all GIS views owned by the user."""

    template_name = "pages/gis_views.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        context = self.get_context_data(**kwargs)

        # Get all active GIS views owned by the user
        context["gis_views"] = (
            GISView.objects.filter(owner=request.user)
            .prefetch_related("project_views__project")
            .order_by("-modified_date")
        )

        # Get or create user token for Personal GIS View
        user_token, _ = Token.objects.get_or_create(user=request.user)

        context["user_token"] = user_token

        return self.render_to_response(context)


class NewGISViewView(AuthenticatedTemplateView):
    """Create a new GIS view."""

    template_name = "pages/gis_view/new.html"


class _BaseGISViewView(AuthenticatedTemplateView):
    """Base class for GIS view detail pages."""

    def get_gis_view_data(self, user: User, gis_view_id: str) -> dict[str, Any]:
        """Get GIS view and verify ownership."""
        gis_view = GISView.objects.prefetch_related("project_views__project").get(
            id=gis_view_id,
            owner=user,
        )

        return {
            "gis_view": gis_view,
            "is_owner": True,  # Always true if we get here
        }


class GISViewDetailsView(_BaseGISViewView):
    """View and edit a GIS view."""

    template_name = "pages/gis_view/details.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        gis_view_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_gis_view_data(
                user=request.user,
                gis_view_id=gis_view_id,
            )
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:gis_views"))

        return super().get(request, *args, **data, **kwargs)


class GISViewGISIntegrationView(_BaseGISViewView):
    """Show GIS integration information (token and API URL)."""

    template_name = "pages/gis_view/gis_integration.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        gis_view_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_gis_view_data(
                user=request.user,
                gis_view_id=gis_view_id,
            )
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:gis_views"))

        return super().get(request, *args, **data, **kwargs)

    def post(
        self,
        request: AuthenticatedHttpRequest,
        gis_view_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        """Handle refresh token POST request."""
        try:
            data = self.get_gis_view_data(
                user=request.user,
                gis_view_id=gis_view_id,
            )
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:gis_views"))

        # Handle token refresh
        if "_refresh_token" in request.POST:
            gis_view = data["gis_view"]
            gis_view.regenerate_token()

        # Redirect back to the same page to show the updated token
        return redirect(
            reverse(
                "private:gis_view_gis_integration",
                kwargs={"gis_view_id": gis_view_id},
            )
        )


class GISViewDangerZoneView(_BaseGISViewView):
    """Delete a GIS view (hard delete)."""

    template_name = "pages/gis_view/danger_zone.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        gis_view_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_gis_view_data(
                user=request.user,
                gis_view_id=gis_view_id,
            )
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:gis_views"))

        return super().get(request, *args, **data, **kwargs)
