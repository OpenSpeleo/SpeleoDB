# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.urls import reverse

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.api.v2.gis_layer_access import accessible_gis_layers_queryset
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISLayerUserPermission

if TYPE_CHECKING:
    from uuid import UUID

    from django.http import HttpResponse
    from django.http.response import HttpResponseRedirectBase

    from speleodb.utils.requests import AuthenticatedHttpRequest


class GISLayerListView(AuthenticatedTemplateView):
    template_name = "pages/gis_layers.html"


class _BaseGISLayerView(AuthenticatedTemplateView):
    def get_layer_data(
        self,
        layer_id: UUID,
        request: AuthenticatedHttpRequest,
    ) -> dict[str, Any]:
        layer = accessible_gis_layers_queryset(user=request.user).get(id=layer_id)
        permission_level = getattr(layer, "user_permission_level", None)

        return {
            "entity": layer,
            "entity_label": "GIS Layer",
            "entity_label_lower": "GIS layer",
            "listing_url": reverse("private:gis_layers"),
            "details_url": reverse(
                "private:gis_layer_details",
                kwargs={"layer_id": layer.id},
            ),
            "permissions_url": reverse(
                "private:gis_layer_user_permissions",
                kwargs={"layer_id": layer.id},
            ),
            "danger_url": reverse(
                "private:gis_layer_danger_zone",
                kwargs={"layer_id": layer.id},
            ),
            "api_detail_url": reverse(
                "api:v2:gis-layer-detail",
                kwargs={"id": layer.id},
            ),
            "download_url": reverse(
                "api:v2:gis-layer-source",
                kwargs={"id": layer.id},
            ),
            "download_label": "Download Source",
            "details_form_id": "gis_layer_details_form",
            "details_method": "PATCH",
            "show_description": True,
            "show_color": True,
            "has_admin_access": permission_level == PermissionLevel.ADMIN,
            "has_write_access": (
                permission_level is not None
                and permission_level >= PermissionLevel.READ_AND_WRITE
            ),
        }


class GISLayerDetailsView(_BaseGISLayerView):
    template_name = "pages/shared/entity_settings/details.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        layer_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_layer_data(layer_id=layer_id, request=request)
        except ObjectDoesNotExist:
            return redirect(reverse("private:gis_layers"))

        data["details_success_message"] = "The GIS layer has been updated."
        return super().get(request, *args, **data, **kwargs)


class GISLayerDangerZoneView(_BaseGISLayerView):
    template_name = "pages/shared/entity_settings/danger_zone.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        layer_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_layer_data(layer_id=layer_id, request=request)
        except ObjectDoesNotExist:
            return redirect(reverse("private:gis_layers"))

        if not data["has_admin_access"]:
            return redirect(data["details_url"])

        data.update(
            danger_success_message="The GIS layer has been deleted successfully.",
        )
        return super().get(request, *args, **data, **kwargs)


class GISLayerUserPermissionsView(_BaseGISLayerView):
    template_name = "pages/shared/entity_settings/user_permissions.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        layer_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        try:
            data = self.get_layer_data(layer_id=layer_id, request=request)
        except ObjectDoesNotExist:
            return redirect(reverse("private:gis_layers"))

        layer = data["entity"]
        permissions = list(
            GISLayerUserPermission.objects.filter(gis_layer=layer, is_active=True)
            .select_related("user")
            .order_by("-level", "user__email")
        )
        data.update(
            permissions=permissions,
            permission_levels=PermissionLevel.members_no_webviewer,
            permission_endpoint=reverse(
                "api:v2:gis-layer-permissions",
                kwargs={"id": layer.id},
            ),
            permission_add_title="Add a collaborator to the GIS Layer",
            permission_success_message="The GIS Layer permission has been saved.",
            permission_delete_message="The GIS Layer permission has been removed.",
        )
        return super().get(request, *args, **data, **kwargs)
