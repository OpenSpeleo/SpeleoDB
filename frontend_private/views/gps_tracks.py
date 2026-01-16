# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.gis.models import GPSTrack

if TYPE_CHECKING:
    from django.http import HttpResponse

    from speleodb.utils.requests import AuthenticatedHttpRequest


class GPSTrackListView(AuthenticatedTemplateView):
    template_name = "pages/gps_tracks.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        context = self.get_context_data(**kwargs)

        context["gps_tracks"] = list(GPSTrack.objects.filter(user=request.user))
        return self.render_to_response(context)


# class NewSurfaceNetworkView(AuthenticatedTemplateView):
#     template_name = "pages/surface_network/new.html"


# class _BaseSurfaceNetworkView(AuthenticatedTemplateView):
#     def get_network_data(self, user: User, network_id: str) -> dict[str, Any]:
#         network = SurfaceMonitoringNetwork.objects.get(id=network_id)

#         user_perm = SurfaceMonitoringNetworkUserPermission.objects.get(
#             user=user,
#             network=network,
#             is_active=True,
#         )

#         return {
#             "network": network,
#             "has_admin_access": user_perm.level == PermissionLevel.ADMIN,
#             "has_write_access": user_perm.level >= PermissionLevel.READ_AND_WRITE,
#         }


# class SurfaceNetworkDetailsView(_BaseSurfaceNetworkView):
#     template_name = "pages/surface_network/details.html"

#     def get(  # type: ignore[override]
#         self,
#         request: AuthenticatedHttpRequest,
#         network_id: str,
#         *args: Any,
#         **kwargs: Any,
#     ) -> HttpResponseRedirectBase | HttpResponse:
#         try:
#             data = self.get_network_data(
#                 user=request.user,
#                 network_id=network_id,
#             )
#         except (ObjectDoesNotExist, PermissionError):
#             return redirect(reverse("private:surface_networks"))

#         return super().get(request, *args, **data, **kwargs)


# class SurfaceNetworkDangerZoneView(_BaseSurfaceNetworkView):
#     template_name = "pages/surface_network/danger_zone.html"

#     def get(  # type: ignore[override]
#         self,
#         request: AuthenticatedHttpRequest,
#         network_id: str,
#         *args: Any,
#         **kwargs: Any,
#     ) -> HttpResponseRedirectBase | HttpResponse:
#         try:
#             data = self.get_network_data(
#                 user=request.user,
#                 network_id=network_id,
#             )
#         except (ObjectDoesNotExist, PermissionError):
#             return redirect(reverse("private:surface_networks"))

#         if not data["has_admin_access"]:
#             return redirect(
#                 reverse(
#                     "private:surface_network_details",
#                     kwargs={"network_id": network_id},
#                 )
#             )

#         return super().get(request, *args, **data, **kwargs)


# class SurfaceNetworkUserPermissionsView(_BaseSurfaceNetworkView):
#     template_name = "pages/surface_network/user_permissions.html"

#     def get(  # type: ignore[override]
#         self,
#         request: AuthenticatedHttpRequest,
#         network_id: str,
#         *args: Any,
#         **kwargs: Any,
#     ) -> HttpResponseRedirectBase | HttpResponse:
#         try:
#             data = self.get_network_data(
#                 user=request.user,
#                 network_id=network_id,
#             )
#         except (ObjectDoesNotExist, PermissionError):
#             return redirect(reverse("private:surface_networks"))

#         data["permissions"] = SurfaceMonitoringNetworkUserPermission.objects.filter(
#             network=data["network"], is_active=True
#         ).prefetch_related("user")

#         return super().get(request, *args, **data, **kwargs)


# class SurfaceNetworkGISView(_BaseSurfaceNetworkView):
#     template_name = "pages/surface_network/gis_integration.html"

#     def get(  # type: ignore[override]
#         self,
#         request: AuthenticatedHttpRequest,
#         network_id: str,
#         *args: Any,
#         **kwargs: Any,
#     ) -> HttpResponseRedirectBase | HttpResponse:
#         try:
#             data = self.get_network_data(
#                 user=request.user,
#                 network_id=network_id,
#             )
#         except (ObjectDoesNotExist, PermissionError):
#             return redirect(reverse("private:surface_networks"))

#         return super().get(request, *args, **data, **kwargs)

#     def post(
#         self,
#         request: AuthenticatedHttpRequest,
#         network_id: str,
#         *args: Any,
#         **kwargs: Any,
#     ) -> HttpResponseRedirectBase | HttpResponse:
#         """Handle refresh token POST request."""
#         try:
#             data = self.get_network_data(
#                 user=request.user,
#                 network_id=network_id,
#             )

#         except (ObjectDoesNotExist, PermissionError):
#             return redirect(reverse("private:surface_networks"))

#         # Only allow admins to refresh the token
#         if "_refresh_token" in request.POST:
#             if not data["has_admin_access"]:
#                 return redirect(
#                     reverse(
#                         "private:surface_network_gis_integration",
#                         kwargs={"network_id": network_id},
#                     )
#                 )

#             network: SurfaceMonitoringNetwork = data["network"]
#             network.refresh_gis_token()

#         # Redirect back to the same page to show the updated token
#         return redirect(
#             reverse(
#                 "private:surface_network_gis_integration",
#                 kwargs={"network_id": network_id},
#             )
#         )
