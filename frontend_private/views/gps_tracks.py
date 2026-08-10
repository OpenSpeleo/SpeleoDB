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

    from speleodb.utils.requests import AuthenticatedHttpRequest


class GPSTrackListView(AuthenticatedTemplateView):
    template_name = "pages/gps_tracks.html"


class GPSTrackUserPermissionsView(AuthenticatedTemplateView):
    template_name = "pages/gps_track/user_permissions.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        track_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        try:
            track = accessible_gps_tracks_queryset(user=request.user).get(id=track_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:gps_tracks"))

        permissions = list(
            GPSTrackUserPermission.objects.filter(
                gps_track=track,
                is_active=True,
            )
            .select_related("user")
            .order_by("-level", "user__email")
        )
        context = self.get_context_data(
            track=track,
            permissions=permissions,
            has_admin_access=(
                getattr(track, "user_permission_level", None) == PermissionLevel.ADMIN
            ),
            **kwargs,
        )
        return self.render_to_response(context)
