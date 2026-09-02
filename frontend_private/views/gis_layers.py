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

    from speleodb.utils.requests import AuthenticatedHttpRequest


class GISLayerListView(AuthenticatedTemplateView):
    template_name = "pages/gis_layers.html"


class GISLayerUserPermissionsView(AuthenticatedTemplateView):
    template_name = "pages/gis_layer/user_permissions.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        layer_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        try:
            layer = accessible_gis_layers_queryset(user=request.user).get(id=layer_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:gis_layers"))

        permissions = list(
            GISLayerUserPermission.objects.filter(gis_layer=layer, is_active=True)
            .select_related("user")
            .order_by("-level", "user__email")
        )
        context = self.get_context_data(
            layer=layer,
            permissions=permissions,
            has_admin_access=(
                getattr(layer, "user_permission_level", None) == PermissionLevel.ADMIN
            ),
            **kwargs,
        )
        return self.render_to_response(context)
