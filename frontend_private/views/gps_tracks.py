# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.urls import reverse

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.api.v2.gps_track_access import accessible_gps_tracks_queryset
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GPSTrackUserPermission

if TYPE_CHECKING:
    from uuid import UUID

    from django.http import HttpResponse
    from django.http.response import HttpResponseRedirectBase

    from speleodb.utils.requests import AuthenticatedHttpRequest


class GPSTrackListView(AuthenticatedTemplateView):
    template_name = "pages/gps_tracks.html"


class _BaseGPSTrackView(AuthenticatedTemplateView):
    def get_track_data(
        self,
        track_id: UUID,
        request: AuthenticatedHttpRequest,
    ) -> dict[str, Any]:
        track = accessible_gps_tracks_queryset(user=request.user).get(id=track_id)
        permission_level = getattr(track, "user_permission_level", None)

        return {
            "entity": track,
            "entity_label": "GPS Track",
            "entity_label_lower": "GPS track",
            "listing_url": reverse("private:gps_tracks"),
            "details_url": reverse(
                "private:gps_track_details",
                kwargs={"track_id": track.id},
            ),
            "permissions_url": reverse(
                "private:gps_track_user_permissions",
                kwargs={"track_id": track.id},
            ),
            "danger_url": reverse(
                "private:gps_track_danger_zone",
                kwargs={"track_id": track.id},
            ),
            "api_detail_url": reverse(
                "api:v2:gps-track-detail",
                kwargs={"id": track.id},
            ),
            "download_url": reverse(
                "api:v2:gps-track-export-gpx",
                kwargs={"id": track.id},
            ),
            "download_label": "Export GPX",
            "details_form_id": "gps_track_details_form",
            "details_method": "PATCH",
            "show_description": False,
            "show_color": True,
            "has_admin_access": permission_level == PermissionLevel.ADMIN,
            "has_write_access": (
                permission_level is not None
                and permission_level >= PermissionLevel.READ_AND_WRITE
            ),
        }


class GPSTrackDetailsView(_BaseGPSTrackView):
    template_name = "pages/shared/entity_settings/details.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        track_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_track_data(track_id=track_id, request=request)
        except ObjectDoesNotExist:
            return redirect(reverse("private:gps_tracks"))

        data["details_success_message"] = "The GPS track has been updated."
        return super().get(request, *args, **data, **kwargs)


class GPSTrackDangerZoneView(_BaseGPSTrackView):
    template_name = "pages/shared/entity_settings/danger_zone.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        track_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_track_data(track_id=track_id, request=request)
        except ObjectDoesNotExist:
            return redirect(reverse("private:gps_tracks"))

        if not data["has_admin_access"]:
            return redirect(data["details_url"])

        data.update(
            danger_success_message="The GPS track has been deleted successfully.",
        )
        return super().get(request, *args, **data, **kwargs)


class GPSTrackUserPermissionsView(_BaseGPSTrackView):
    template_name = "pages/shared/entity_settings/user_permissions.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        track_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        try:
            data = self.get_track_data(track_id=track_id, request=request)
        except ObjectDoesNotExist:
            return redirect(reverse("private:gps_tracks"))

        track = data["entity"]
        permissions = list(
            GPSTrackUserPermission.objects.filter(
                gps_track=track,
                is_active=True,
            )
            .select_related("user")
            .order_by("-level", "user__email")
        )
        data.update(
            permissions=permissions,
            permission_levels=PermissionLevel.members_no_webviewer,
            permission_endpoint=reverse(
                "api:v2:gps-track-permissions",
                kwargs={"id": track.id},
            ),
            permission_add_title="Add a collaborator to the GPS track",
            permission_success_message="The GPS track permission has been saved.",
            permission_delete_message="The GPS track permission has been removed.",
        )
        return super().get(request, *args, **data, **kwargs)
