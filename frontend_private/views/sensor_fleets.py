# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Case
from django.db.models import OuterRef
from django.db.models import Prefetch
from django.db.models import Q
from django.db.models import Subquery
from django.db.models import Value
from django.db.models import When
from django.db.models.functions import Least
from django.db.models.functions import Lower
from django.shortcuts import redirect
from django.urls import reverse
from pydantic import BaseModel
from pydantic import ConfigDict

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Sensor
from speleodb.gis.models import SensorFleet
from speleodb.gis.models import SensorFleetUserPermission
from speleodb.gis.models import SensorInstall
from speleodb.gis.models import Station
from speleodb.gis.models.sensor import InstallStatus
from speleodb.utils.pydantic_utils import NotFutureDate  # noqa: TC001

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

        sensors = (
            sensor_fleet.sensors.all()
            .order_by(Lower("name"))
            .prefetch_related(
                Prefetch(
                    "installs",
                    queryset=SensorInstall.objects.filter(
                        status=InstallStatus.INSTALLED
                    ).select_related("station", "station__project"),
                    to_attr="active_installs",
                )
            )
        )

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


class SensorInstallEvent(BaseModel):
    date: NotFutureDate
    event: InstallStatus
    sensor: Sensor
    station: Station
    user: str

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SensorFleetHistoryView(_BaseSensorFleetView):
    template_name = "pages/sensor_fleet/history.html"

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

        # Fetch all installs for this fleet, ordered by modified_date desc
        installs = (
            SensorInstall.objects.filter(sensor__fleet=data["sensor_fleet"])
            .select_related("sensor", "station", "station__project")
            .order_by("-modified_date")
        )

        # data["installs"] = installs
        processed_events: list[SensorInstallEvent] = []
        for install in installs:
            processed_events.append(
                SensorInstallEvent(
                    date=install.install_date,
                    event=InstallStatus.INSTALLED,
                    sensor=install.sensor,
                    station=install.station,
                    user=install.install_user,
                )
            )

            if install.status != InstallStatus.INSTALLED:
                processed_events.append(
                    SensorInstallEvent(
                        date=(
                            install.uninstall_date
                            if install.uninstall_date
                            else install.modified_date.date()
                        ),
                        event=install.status,  # type: ignore[arg-type]
                        sensor=install.sensor,
                        station=install.station,
                        user=install.uninstall_user if install.uninstall_user else "-",
                    )
                )

        data["installs"] = sorted(
            processed_events,
            key=lambda event: event.date,
            reverse=True,
        )

        return super().get(request, *args, **data, **kwargs)


class SensorFleetWatchlistView(_BaseSensorFleetView):
    template_name = "pages/sensor_fleet/watchlist.html"

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

        # Get days parameter from query string, default to 60 (2 months)
        days_param = request.GET.get("days", "60")
        try:
            days = int(days_param)
            if days < 0:
                days = 60  # Default to 60 if invalid
        except ValueError:
            days = 60  # Default to 60 if invalid

        # Get installs due for retrieval for sensors in this fleet
        due_installs = (
            SensorInstall.objects.due_for_retrieval(days=days)  # pyright: ignore[reportAttributeAccessIssue]
            .filter(sensor__fleet=data["sensor_fleet"])
            .select_related("sensor", "station", "station__project")
        )

        # Get unique sensors from the installs
        sensor_ids = due_installs.values_list("sensor_id", flat=True).distinct()

        # Annotate sensors with minimum expiry date from their active installs
        active_installs = SensorInstall.objects.filter(
            sensor=OuterRef("pk"),
            status=InstallStatus.INSTALLED,
        )

        sensors = (
            data["sensor_fleet"]
            .sensors.filter(id__in=sensor_ids)
            .annotate(
                min_expiry_date=Subquery(
                    active_installs.annotate(
                        min_expiry=Case(
                            # Both dates exist: use Least
                            When(
                                Q(expiracy_memory_date__isnull=False)
                                & Q(expiracy_battery_date__isnull=False),
                                then=Least(
                                    "expiracy_memory_date", "expiracy_battery_date"
                                ),
                            ),
                            # Only memory date exists
                            When(
                                Q(expiracy_memory_date__isnull=False)
                                & Q(expiracy_battery_date__isnull=True),
                                then="expiracy_memory_date",
                            ),
                            # Only battery date exists
                            When(
                                Q(expiracy_memory_date__isnull=True)
                                & Q(expiracy_battery_date__isnull=False),
                                then="expiracy_battery_date",
                            ),
                            # Both NULL: use NULL (will sort last)
                            default=Value(None),
                        )
                    ).values("min_expiry")[:1]
                )
            )
            .prefetch_related(
                Prefetch(
                    "installs",
                    queryset=SensorInstall.objects.filter(
                        status=InstallStatus.INSTALLED
                    ).select_related("station", "station__project"),
                    to_attr="active_installs",
                )
            )
            .order_by("min_expiry_date", "-modified_date")
        )

        data["sensors"] = sensors
        data["days"] = days

        return super().get(request, *args, **data, **kwargs)
