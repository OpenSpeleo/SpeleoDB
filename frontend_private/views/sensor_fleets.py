# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db.models.functions import Lower
from django.shortcuts import redirect
from django.urls import reverse

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import SensorFleet
from speleodb.gis.models import SensorFleetUserPermission

if TYPE_CHECKING:
    from django.http import HttpResponse
    from django.http.response import HttpResponseRedirectBase

    from speleodb.users.models import User
    from speleodb.utils.requests import AuthenticatedHttpRequest


class SensorFleetListingView(AuthenticatedTemplateView):
    template_name = "pages/sensor_fleets.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        context = self.get_context_data(**kwargs)

        context["sensorfleet_perms"] = SensorFleetUserPermission.objects.filter(
            user=request.user,
            is_active=True,
            sensor_fleet__is_active=True,
        ).prefetch_related("sensor_fleet")
        return self.render_to_response(context)


class NewSensorFleetView(AuthenticatedTemplateView):
    template_name = "pages/sensor_fleet/new.html"


class _BaseSensorFleetView(AuthenticatedTemplateView):
    def get_sensor_fleet_data(self, user: User, fleet_id: str) -> dict[str, Any]:
        sensor_fleet = SensorFleet.objects.get(id=fleet_id)

        user_perm = SensorFleetUserPermission.objects.get(
            user=user,
            sensor_fleet=sensor_fleet,
            is_active=True,
        )

        sensors = sensor_fleet.sensors.all().order_by(Lower("name"))

        return {
            "sensor_fleet": sensor_fleet,
            "sensors": sensors,
            "has_admin_access": user_perm.level == PermissionLevel.ADMIN,
            "has_write_access": user_perm.level >= PermissionLevel.READ_AND_WRITE,
        }


class SensorFleetDetailsView(_BaseSensorFleetView):
    template_name = "pages/sensor_fleet/details.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        fleet_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_sensor_fleet_data(
                user=request.user,
                fleet_id=fleet_id,
            )
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:sensor_fleets"))

        return super().get(request, *args, **data, **kwargs)


class SensorFleetDangerZoneView(_BaseSensorFleetView):
    template_name = "pages/sensor_fleet/danger_zone.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        fleet_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_sensor_fleet_data(
                user=request.user,
                fleet_id=fleet_id,
            )
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:sensor_fleets"))

        if not data["has_admin_access"]:
            return redirect(
                reverse(
                    "private:sensor_fleet_details",
                    kwargs={"fleet_id": fleet_id},
                )
            )

        return super().get(request, *args, **data, **kwargs)


class SensorFleetUserPermissionsView(_BaseSensorFleetView):
    template_name = "pages/sensor_fleet/user_permissions.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        fleet_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_sensor_fleet_data(
                user=request.user,
                fleet_id=fleet_id,
            )
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:sensor_fleets"))

        data["permissions"] = SensorFleetUserPermission.objects.filter(
            sensor_fleet=data["sensor_fleet"], is_active=True
        ).prefetch_related("user")

        return super().get(request, *args, **data, **kwargs)
