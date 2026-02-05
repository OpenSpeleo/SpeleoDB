# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
from django.db.models.functions import Lower
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from pydantic import BaseModel
from pydantic import ConfigDict

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.common.enums import InstallStatus
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Cylinder
from speleodb.gis.models import CylinderFleet
from speleodb.gis.models import CylinderFleetUserPermission
from speleodb.gis.models import CylinderInstall
from speleodb.utils.pydantic_utils import NotFutureDate  # noqa: TC001

if TYPE_CHECKING:
    from django.http import HttpResponse
    from django.http.response import HttpResponseRedirectBase

    from speleodb.users.models import User
    from speleodb.utils.requests import AuthenticatedHttpRequest


class CylinderFleetListingView(AuthenticatedTemplateView):
    template_name = "pages/cylinder_fleets.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        context = self.get_context_data(**kwargs)

        context["cylinderfleet_perms"] = list(
            CylinderFleetUserPermission.objects.filter(
                user=request.user,
                is_active=True,
                cylinder_fleet__is_active=True,
            ).prefetch_related("cylinder_fleet")
        )
        return self.render_to_response(context)


class NewCylinderFleetView(AuthenticatedTemplateView):
    template_name = "pages/cylinder_fleet/new.html"


class _BaseCylinderFleetView(AuthenticatedTemplateView):
    def get_cylinder_fleet_data(self, user: User, fleet_id: str) -> dict[str, Any]:
        cylinder_fleet = CylinderFleet.objects.get(id=fleet_id)

        user_perm = CylinderFleetUserPermission.objects.get(
            user=user,
            cylinder_fleet=cylinder_fleet,
            is_active=True,
        )

        cylinders = (
            cylinder_fleet.cylinders.all()
            .order_by(Lower("name"))
            .prefetch_related(
                Prefetch(
                    "installs",
                    queryset=CylinderInstall.objects.filter(
                        status=InstallStatus.INSTALLED
                    ).select_related("project"),
                    to_attr="active_installs",
                )
            )
        )

        return {
            "cylinder_fleet": cylinder_fleet,
            "cylinders": cylinders,
            "has_admin_access": user_perm.level == PermissionLevel.ADMIN,
            "has_write_access": user_perm.level >= PermissionLevel.READ_AND_WRITE,
        }


class CylinderFleetDetailsView(_BaseCylinderFleetView):
    template_name = "pages/cylinder_fleet/details.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        fleet_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_cylinder_fleet_data(
                user=request.user,
                fleet_id=fleet_id,
            )
        except ObjectDoesNotExist, PermissionError:
            return redirect(reverse("private:cylinder_fleets"))

        return super().get(request, *args, **data, **kwargs)


class CylinderFleetDangerZoneView(_BaseCylinderFleetView):
    template_name = "pages/cylinder_fleet/danger_zone.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        fleet_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_cylinder_fleet_data(
                user=request.user,
                fleet_id=fleet_id,
            )
        except ObjectDoesNotExist, PermissionError:
            return redirect(reverse("private:cylinder_fleets"))

        if not data["has_admin_access"]:
            return redirect(
                reverse(
                    "private:cylinder_fleet_details",
                    kwargs={"fleet_id": fleet_id},
                )
            )

        return super().get(request, *args, **data, **kwargs)


class CylinderFleetUserPermissionsView(_BaseCylinderFleetView):
    template_name = "pages/cylinder_fleet/user_permissions.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        fleet_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_cylinder_fleet_data(
                user=request.user,
                fleet_id=fleet_id,
            )
        except ObjectDoesNotExist, PermissionError:
            return redirect(reverse("private:cylinder_fleets"))

        data["permissions"] = CylinderFleetUserPermission.objects.filter(
            cylinder_fleet=data["cylinder_fleet"], is_active=True
        ).prefetch_related("user")

        return super().get(request, *args, **data, **kwargs)


class CylinderInstallEvent(BaseModel):
    date: NotFutureDate
    event: InstallStatus
    cylinder: Cylinder
    location_name: str
    latitude: float
    longitude: float
    user: str

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CylinderFleetHistoryView(_BaseCylinderFleetView):
    template_name = "pages/cylinder_fleet/history.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        fleet_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_cylinder_fleet_data(
                user=request.user,
                fleet_id=fleet_id,
            )
        except ObjectDoesNotExist, PermissionError:
            return redirect(reverse("private:cylinder_fleets"))

        installs = (
            CylinderInstall.objects.filter(cylinder__fleet=data["cylinder_fleet"])
            .select_related("cylinder")
            .order_by("-modified_date")
        )

        processed_events: list[CylinderInstallEvent] = []
        for install in installs:
            processed_events.append(
                CylinderInstallEvent(
                    date=install.install_date,
                    event=InstallStatus.INSTALLED,
                    cylinder=install.cylinder,
                    location_name=install.location_name,
                    latitude=float(install.latitude),
                    longitude=float(install.longitude),
                    user=install.install_user,
                )
            )

            if install.status != InstallStatus.INSTALLED:
                processed_events.append(
                    CylinderInstallEvent(
                        date=(
                            install.uninstall_date
                            if install.uninstall_date
                            else install.modified_date.date()
                        ),
                        event=install.status,  # type: ignore[arg-type]
                        cylinder=install.cylinder,
                        location_name=install.location_name,
                        latitude=float(install.latitude),
                        longitude=float(install.longitude),
                        user=install.uninstall_user if install.uninstall_user else "-",
                    )
                )

        data["installs"] = sorted(
            processed_events,
            key=lambda event: event.date,
            reverse=True,
        )

        return super().get(request, *args, **data, **kwargs)


class CylinderFleetWatchlistView(_BaseCylinderFleetView):
    template_name = "pages/cylinder_fleet/watchlist.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        fleet_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_cylinder_fleet_data(
                user=request.user,
                fleet_id=fleet_id,
            )
        except ObjectDoesNotExist, PermissionError:
            return redirect(reverse("private:cylinder_fleets"))

        # Get days parameter from query string, default to 60
        days_param = request.GET.get("days", "60")
        try:
            days = int(days_param)
            if days < 0:
                days = 60  # Default to 60 if invalid
        except ValueError:
            days = 60  # Default to 60 if invalid

        today = timezone.localdate()
        cutoff_date = today - timedelta(days=days)

        due_installs = (
            CylinderInstall.objects.filter(
                cylinder__fleet=data["cylinder_fleet"],
                status=InstallStatus.INSTALLED,
                install_date__lte=cutoff_date,
            )
            .select_related("cylinder")
            .order_by("install_date")
        )

        cylinder_ids = due_installs.values_list("cylinder_id", flat=True).distinct()

        cylinders = (
            data["cylinder_fleet"]
            .cylinders.filter(id__in=cylinder_ids)
            .prefetch_related(
                Prefetch(
                    "installs",
                    queryset=CylinderInstall.objects.filter(
                        status=InstallStatus.INSTALLED
                    ),
                    to_attr="active_installs",
                )
            )
            .order_by(Lower("name"))
        )

        data["cylinders"] = list(cylinders)
        data["days"] = days

        return super().get(request, *args, **data, **kwargs)
