# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.urls import reverse

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.api.v2.gis_geometry_access import accessible_gis_geometries_queryset
from speleodb.common.enums import PermissionLevel
from speleodb.gis.geometry_validation import GIS_GEOMETRY_MAX_AREA_KM2
from speleodb.gis.geometry_validation import GIS_GEOMETRY_MAX_VERTICES
from speleodb.gis.geometry_validation import GIS_GEOMETRY_TYPES
from speleodb.gis.models import GISGeometryUserPermission

if TYPE_CHECKING:
    from uuid import UUID

    from django.http import HttpResponse
    from django.http.response import HttpResponseRedirectBase

    from speleodb.gis.models import GISGeometry
    from speleodb.utils.requests import AuthenticatedHttpRequest


class GISGeometryListView(AuthenticatedTemplateView):
    template_name = "pages/gis_geometries.html"


class _BaseGISGeometryView(AuthenticatedTemplateView):
    def get_geometry_data(
        self,
        geometry_id: UUID,
        request: AuthenticatedHttpRequest,
    ) -> dict[str, Any]:
        geometry: GISGeometry = accessible_gis_geometries_queryset(
            user=request.user
        ).get(id=geometry_id)
        permission_level: int | None = getattr(geometry, "user_permission_level", None)

        return {
            "entity": geometry,
            "entity_label": "GIS Geometry",
            "entity_label_lower": "GIS geometry",
            "listing_url": reverse("private:gis_geometries"),
            "details_url": reverse(
                "private:gis_geometry_details",
                kwargs={"geometry_id": geometry.id},
            ),
            "permissions_url": reverse(
                "private:gis_geometry_user_permissions",
                kwargs={"geometry_id": geometry.id},
            ),
            "danger_url": reverse(
                "private:gis_geometry_danger_zone",
                kwargs={"geometry_id": geometry.id},
            ),
            "api_detail_url": reverse(
                "api:v2:gis-geometry-detail",
                kwargs={"id": geometry.id},
            ),
            "map_url": f"{reverse('private:map_viewer')}?geometry={geometry.id}",
            "geojson_text": json.dumps(geometry.geojson, indent=2),
            "geometry_max_area_km2": GIS_GEOMETRY_MAX_AREA_KM2,
            "geometry_max_vertices": GIS_GEOMETRY_MAX_VERTICES,
            "geometry_supported_types": " or ".join(sorted(GIS_GEOMETRY_TYPES)),
            "details_form_id": "gis_geometry_details_form",
            "details_method": "PATCH",
            "show_description": False,
            "show_color": True,
            "has_admin_access": permission_level == PermissionLevel.ADMIN,
            "has_write_access": (
                permission_level is not None
                and permission_level >= PermissionLevel.READ_AND_WRITE
            ),
        }


class GISGeometryDetailsView(_BaseGISGeometryView):
    template_name = "pages/gis_geometry/details.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        geometry_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data: dict[str, Any] = self.get_geometry_data(
                geometry_id=geometry_id, request=request
            )
        except ObjectDoesNotExist:
            return redirect(reverse("private:gis_geometries"))

        data["details_success_message"] = "The GIS geometry has been updated."
        return super().get(request, *args, **data, **kwargs)


class GISGeometryDangerZoneView(_BaseGISGeometryView):
    template_name = "pages/shared/entity_settings/danger_zone.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        geometry_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data: dict[str, Any] = self.get_geometry_data(
                geometry_id=geometry_id, request=request
            )
        except ObjectDoesNotExist:
            return redirect(reverse("private:gis_geometries"))

        if not data["has_admin_access"]:
            return redirect(data["details_url"])

        data.update(
            danger_success_message="The GIS geometry has been deleted successfully.",
        )
        return super().get(request, *args, **data, **kwargs)


class GISGeometryUserPermissionsView(_BaseGISGeometryView):
    template_name = "pages/shared/entity_settings/user_permissions.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        geometry_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        try:
            data: dict[str, Any] = self.get_geometry_data(
                geometry_id=geometry_id, request=request
            )
        except ObjectDoesNotExist:
            return redirect(reverse("private:gis_geometries"))

        geometry: GISGeometry = data["entity"]
        permissions: list[GISGeometryUserPermission] = list(
            GISGeometryUserPermission.objects.filter(
                gis_geometry=geometry, is_active=True
            )
            .select_related("user")
            .order_by("-level", "user__email")
        )
        data.update(
            permissions=permissions,
            permission_levels=PermissionLevel.members_no_webviewer,
            permission_endpoint=reverse(
                "api:v2:gis-geometry-permissions",
                kwargs={"id": geometry.id},
            ),
            permission_add_title="Add a collaborator to the GIS Geometry",
            permission_success_message="The GIS Geometry permission has been saved.",
            permission_delete_message="The GIS Geometry permission has been removed.",
        )
        return super().get(request, *args, **data, **kwargs)
