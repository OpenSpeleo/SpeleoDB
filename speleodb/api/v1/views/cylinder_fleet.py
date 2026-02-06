# -*- coding: utf-8 -*-

from __future__ import annotations

import io
import logging
import re
from datetime import timedelta
from typing import TYPE_CHECKING
from typing import Any
from uuid import UUID

import xlsxwriter
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from django.db.models import Exists
from django.db.models import IntegerField
from django.db.models import OuterRef
from django.db.models import Prefetch
from django.db.models import Subquery
from django.http import Http404
from django.http import StreamingHttpResponse
from django.utils import timezone
from geojson import FeatureCollection  # type: ignore[attr-defined]
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import IsObjectCreation
from speleodb.api.v1.permissions import IsObjectDeletion
from speleodb.api.v1.permissions import IsObjectEdition
from speleodb.api.v1.permissions import IsReadOnly
from speleodb.api.v1.permissions import SDB_AdminAccess
from speleodb.api.v1.permissions import SDB_ReadAccess
from speleodb.api.v1.permissions import SDB_WriteAccess
from speleodb.api.v1.serializers import CylinderFleetSerializer
from speleodb.api.v1.serializers import CylinderFleetUserPermissionSerializer
from speleodb.api.v1.serializers import CylinderFleetWithPermSerializer
from speleodb.api.v1.serializers import CylinderInstallGeoJSONSerializer
from speleodb.api.v1.serializers import CylinderInstallSerializer
from speleodb.api.v1.serializers import CylinderPressureCheckSerializer
from speleodb.api.v1.serializers import CylinderSerializer
from speleodb.common.enums import InstallStatus
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Cylinder
from speleodb.gis.models import CylinderFleet
from speleodb.gis.models import CylinderFleetUserPermission
from speleodb.gis.models import CylinderInstall
from speleodb.gis.models import CylinderPressureCheck
from speleodb.users.models import User
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.exceptions import BadRequestError
from speleodb.utils.exceptions import NotAuthorizedError
from speleodb.utils.exceptions import UserNotActiveError
from speleodb.utils.exceptions import UserNotFoundError
from speleodb.utils.exceptions import ValueNotFoundError
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import NoWrapResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response

logger = logging.getLogger(__name__)


class CylinderFleetApiView(GenericAPIView[CylinderFleet], SDBAPIViewMixin):
    """
    GET: List all cylinder fleets accessible to the authenticated user
    POST: Create a new cylinder fleet
    """

    queryset = CylinderFleet.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CylinderFleetSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List all cylinder fleets with user permissions."""
        user = self.get_user()

        perm_qs = CylinderFleetUserPermission.objects.filter(
            cylinder_fleet=OuterRef("pk"),
            user=user,
            is_active=True,
        )

        fleets = (
            CylinderFleet.objects.filter(is_active=True)
            .filter(Exists(perm_qs))
            .annotate(
                cylinder_count=Count("cylinders", distinct=True),
                user_permission_level=Subquery(
                    perm_qs.values("level")[:1],
                    output_field=IntegerField(),
                ),
            )
            .distinct()
        )

        return SuccessResponse(CylinderFleetWithPermSerializer(fleets, many=True).data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new cylinder fleet."""
        user = self.get_user()

        data = request.data.copy()

        # Add created_by to data
        data["created_by"] = user.email

        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)


class CylinderFleetSpecificApiView(GenericAPIView[CylinderFleet], SDBAPIViewMixin):
    """
    GET: Retrieve a specific cylinder fleet
    PUT/PATCH: Update a cylinder fleet
    DELETE: Deactivate a cylinder fleet
    """

    queryset = CylinderFleet.objects.all()
    permission_classes = [
        (IsObjectDeletion & SDB_AdminAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = CylinderFleetSerializer
    lookup_field = "id"
    lookup_url_kwarg = "fleet_id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Retrieve a specific cylinder fleet."""
        cylinder_fleet = self.get_object()
        serializer = self.get_serializer(cylinder_fleet)
        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        """Update a cylinder fleet."""
        cylinder_fleet = self.get_object()
        serializer = self.get_serializer(
            cylinder_fleet, data=request.data, partial=partial
        )

        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Full update of cylinder fleet."""
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Partial update of cylinder fleet."""
        return self._modify_obj(request=request, partial=True, **kwargs)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Deactivate a cylinder fleet instead of deleting it.

        Sets is_active=False to deactivate the fleet while preserving
        all data. Also deactivates all user permissions for the fleet.
        """
        user = self.get_user()
        cylinder_fleet = self.get_object()

        # Deactivate all permissions
        for perm in cylinder_fleet.user_permissions.all():
            perm.deactivate(deactivated_by=user)

        # Deactivate the fleet
        cylinder_fleet.is_active = False
        cylinder_fleet.save()

        return SuccessResponse(
            {
                "id": str(cylinder_fleet.id),
                "message": "Cylinder fleet deleted successfully",
            }
        )


class CylinderApiView(GenericAPIView[CylinderFleet], SDBAPIViewMixin):
    """
    GET: List all cylinders in a fleet
    POST: Create a new cylinder in a fleet
    """

    queryset = CylinderFleet.objects.all()
    permission_classes = [
        (IsObjectCreation & SDB_WriteAccess) | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = CylinderFleetSerializer
    lookup_field = "id"
    lookup_url_kwarg = "fleet_id"

    def get(
        self, request: Request, fleet_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """List all cylinders in a fleet."""
        fleet = self.get_object()

        cylinders = Cylinder.objects.filter(fleet=fleet).order_by("name")
        serializer = CylinderSerializer(cylinders, many=True)
        return SuccessResponse(serializer.data)

    def post(
        self, request: Request, fleet_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """Create a new cylinder in a fleet."""
        user = self.get_user()
        fleet = self.get_object()

        # Add fleet and created_by to data
        data = request.data.copy()
        data["fleet"] = fleet.id
        data["created_by"] = user.email

        serializer = CylinderSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class CylinderSpecificApiView(GenericAPIView[Cylinder], SDBAPIViewMixin):
    """
    GET: Retrieve a specific cylinder
    PUT/PATCH: Update a cylinder
    DELETE: Delete a cylinder
    """

    queryset = Cylinder.objects.all()
    permission_classes = [
        (IsObjectDeletion & SDB_WriteAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = CylinderSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Retrieve a specific cylinder."""
        cylinder = self.get_object()
        serializer = self.get_serializer(cylinder)
        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        """Update a cylinder."""
        cylinder = self.get_object()
        serializer = self.get_serializer(cylinder, data=request.data, partial=partial)

        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Full update of cylinder."""
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Partial update of cylinder."""
        return self._modify_obj(request=request, partial=True, **kwargs)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete a cylinder permanently."""
        cylinder = self.get_object()
        cylinder_id = cylinder.id
        cylinder.delete()

        return SuccessResponse(
            {"id": str(cylinder_id), "message": "Cylinder deleted successfully"}
        )


class CylinderFleetPermissionApiView(GenericAPIView[CylinderFleet], SDBAPIViewMixin):
    """
    GET: List all permissions for a fleet
    POST: Grant permission to a user
    """

    queryset = CylinderFleet.objects.all()
    permission_classes = [SDB_AdminAccess | (IsReadOnly & SDB_ReadAccess)]
    serializer_class = CylinderFleetSerializer
    lookup_field = "id"
    lookup_url_kwarg = "fleet_id"

    def _process_request_data(
        self, request: Request, data: dict[str, Any], skip_level: bool = False
    ) -> dict[str, Any]:
        request_user = self.get_user()
        perm_data: dict[str, Any] = {}

        for key in ["user", "level"]:
            try:
                if key == "level" and skip_level:
                    continue

                value = data[key]

                match key:
                    case "level":
                        if not isinstance(value, str) or value.upper() not in [
                            name for _, name in PermissionLevel.choices_no_webviewer
                        ]:
                            raise BadRequestError(
                                f"Invalid value received for `{key}`: `{value}`"
                            )

                        try:
                            perm_data[key] = PermissionLevel.from_str(value.upper())
                        except AttributeError as e:
                            raise ValueNotFoundError(
                                f"The user permission level: `{value.upper()}` does "
                                "not exist."
                            ) from e

                    case "user":
                        try:
                            user = User.objects.get(email=value)
                        except ObjectDoesNotExist as e:
                            raise UserNotFoundError(
                                f"The user: `{value}` does not exist."
                            ) from e

                        if request_user == user:
                            raise NotAuthorizedError(
                                "A user can not edit their own permission"
                            )

                        if not user.is_active:
                            raise UserNotActiveError(
                                f"The user: `{value}` is inactive."
                            )

                        perm_data["user"] = user

                    case _:
                        raise ValueNotFoundError(f"Unknown key: {key}")

            except KeyError as e:
                raise ValueNotFoundError(
                    f"Attribute: `{key}` is missing. {data}"
                ) from e

        return perm_data

    def get(
        self, request: Request, fleet_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """List all active permissions for a fleet."""
        fleet = self.get_object()

        permissions = CylinderFleetUserPermission.objects.filter(
            cylinder_fleet=fleet,
            is_active=True,
        ).select_related("user")

        serializer = CylinderFleetUserPermissionSerializer(permissions, many=True)
        return SuccessResponse(serializer.data)

    def post(
        self, request: Request, fleet_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """Grant permission to a user (requires ADMIN access)."""
        fleet = self.get_object()

        perm_data = self._process_request_data(request=request, data=request.data)

        target_user: User = perm_data["user"]
        permission, created = CylinderFleetUserPermission.objects.get_or_create(
            user=target_user,
            cylinder_fleet=fleet,
        )

        if not created:
            if permission.is_active:
                return ErrorResponse(
                    {
                        "error": (
                            f"A permission for this user: `{target_user}` "
                            "already exist."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            permission.reactivate(level=perm_data["level"])

        else:
            permission.level = perm_data["level"]

        permission.save()

        permission_serializer = CylinderFleetUserPermissionSerializer(permission)
        fleet_serializer = self.get_serializer(fleet)

        # Refresh the `modified_date` field
        fleet.save()

        return SuccessResponse(
            {
                "fleet": fleet_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        fleet = self.get_object()
        user = self.get_user()

        perm_data = self._process_request_data(request=request, data=request.data)

        if user == perm_data["user"]:
            return ErrorResponse(
                {"error": ("A user can not edit their own permission")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_user: User = perm_data["user"]
        try:
            permission = CylinderFleetUserPermission.objects.get(
                user=target_user,
                cylinder_fleet=fleet,
            )

        except ObjectDoesNotExist as e:
            raise Http404(
                f"A permission for this user: `{target_user}` does not exist."
            ) from e

        permission.level = perm_data["level"]
        permission.save()

        permission_serializer = CylinderFleetUserPermissionSerializer(permission)
        fleet_serializer = self.get_serializer(fleet)

        fleet.save()
        return SuccessResponse(
            {
                "fleet": fleet_serializer.data,
                "permission": permission_serializer.data,
            }
        )

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        fleet = self.get_object()
        user = self.get_user()

        perm_data = self._process_request_data(
            request=request, data=request.data, skip_level=True
        )

        if user == perm_data["user"]:
            return ErrorResponse(
                {"error": ("A user can not edit their own permission")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_user: User = perm_data["user"]
        try:
            permission = CylinderFleetUserPermission.objects.get(
                cylinder_fleet=fleet,
                user=target_user,
                is_active=True,
            )

        except ObjectDoesNotExist as e:
            raise Http404(
                f"A permission for this user: `{target_user}` does not exist."
            ) from e

        permission.deactivate(deactivated_by=user)

        fleet_serializer = self.get_serializer(fleet)

        # Refresh the `modified_date` field
        fleet.save()

        return SuccessResponse(
            {
                "fleet": fleet_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class CylinderFleetExportExcelApiView(GenericAPIView[CylinderFleet], SDBAPIViewMixin):
    """
    Export cylinder fleet cylinders to Excel format.

    GET: Download Excel file containing all cylinders in a fleet.
    """

    queryset = CylinderFleet.objects.all()
    permission_classes = [(IsReadOnly & SDB_ReadAccess)]
    lookup_field = "id"
    lookup_url_kwarg = "fleet_id"
    serializer_class = CylinderSerializer  # type: ignore[assignment]

    def get(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response | StreamingHttpResponse:
        """Export fleet cylinders to Excel."""
        fleet = self.get_object()

        cylinders = (
            Cylinder.objects.filter(fleet=fleet)
            .prefetch_related("installs")
            .order_by("-modified_date")
        )

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Cylinders")

        header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#4F46E5",
                "font_color": "white",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )

        cell_format = workbook.add_format({"border": 1, "valign": "top"})

        headers = [
            "Cylinder Name",
            "Serial",
            "Brand",
            "Owner",
            "Type",
            "Status",
            "O2 %",
            "He %",
            "N2 %",
            "Pressure",
            "Unit System",
            "Use Anode",
            "Manufactured",
            "Last Visual",
            "Last Hydro",
            "Location",
            "Lat",
            "Long",
            "Install Date",
            "Modified Date",
        ]

        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, header_format)
            worksheet.set_column(col_num, col_num, max(len(header) + 2, 15))

        for row_num, cylinder in enumerate(cylinders, start=1):
            latest_install = cylinder.installs.filter(
                status=InstallStatus.INSTALLED
            ).first()

            row_data = [
                cylinder.name,
                cylinder.serial,
                cylinder.brand,
                cylinder.owner,
                cylinder.type,
                cylinder.status.title(),
                cylinder.o2_percentage,
                cylinder.he_percentage,
                cylinder.n2_percentage,
                cylinder.pressure,
                cylinder.unit_system,
                "Yes" if cylinder.use_anode else "No",
                cylinder.manufactured_date.isoformat()
                if cylinder.manufactured_date
                else "",
                cylinder.last_visual_inspection_date.isoformat()
                if cylinder.last_visual_inspection_date
                else "",
                cylinder.last_hydrostatic_test_date.isoformat()
                if cylinder.last_hydrostatic_test_date
                else "",
                latest_install.location_name if latest_install else "",
                float(latest_install.latitude) if latest_install else "",
                float(latest_install.longitude) if latest_install else "",
                latest_install.install_date.isoformat()
                if latest_install and latest_install.install_date
                else "",
                cylinder.modified_date.strftime("%Y-%m-%d %H:%M:%S"),
            ]

            for col_num, cell_value in enumerate(row_data):
                worksheet.write(row_num, col_num, cell_value, cell_format)

        workbook.close()
        output.seek(0)

        filename = (
            f"cylinder_fleet_{fleet.name}_{timezone.localdate().isoformat()}.xlsx"
        )
        filename = re.sub(r'[\\/*?:"<>|]', "", filename)

        response = StreamingHttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response


class CylinderFleetWatchlistApiView(GenericAPIView[CylinderFleet], SDBAPIViewMixin):
    """
    GET: List cylinders in a fleet that are due for retrieval.

    Query Parameters:
        days (optional): Number of days installed to include (default: 60).
    """

    queryset = CylinderFleet.objects.all()
    permission_classes = [(IsReadOnly & SDB_ReadAccess)]
    serializer_class = CylinderSerializer  # type: ignore[assignment]
    lookup_field = "id"
    lookup_url_kwarg = "fleet_id"

    def get(
        self, request: Request, fleet_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """List cylinders in a fleet that are due for retrieval."""
        fleet = self.get_object()

        days_param = request.query_params.get("days", "60")
        try:
            days = int(days_param)
            if days < 0:
                return ErrorResponse(
                    {"error": "Days parameter must be a non-negative integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            return ErrorResponse(
                {"error": "Days parameter must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cutoff_date = timezone.localdate() - timedelta(days=days)

        due_installs = (
            CylinderInstall.objects.filter(
                cylinder__fleet=fleet,
                status=InstallStatus.INSTALLED,
                install_date__lte=cutoff_date,
            )
            .select_related("cylinder", "project")
            .prefetch_related("cylinder__fleet")
            .order_by("install_date")
        )

        cylinder_ids = due_installs.values_list("cylinder_id", flat=True).distinct()

        cylinders = (
            Cylinder.objects.filter(id__in=cylinder_ids, fleet=fleet)
            .prefetch_related(
                Prefetch(
                    "installs",
                    queryset=CylinderInstall.objects.filter(
                        status=InstallStatus.INSTALLED
                    ),
                    to_attr="active_installs",
                )
            )
            .order_by("name")
        )

        serializer = CylinderSerializer(cylinders, many=True)
        return SuccessResponse(serializer.data)


class CylinderFleetWatchlistExportExcelApiView(
    GenericAPIView[CylinderFleet], SDBAPIViewMixin
):
    """
    Export watchlist cylinders to Excel format.

    GET: Download Excel file containing cylinders due for retrieval.
    Query Parameters:
        days (optional): Number of days installed to include (default: 60).
    """

    queryset = CylinderFleet.objects.all()
    permission_classes = [(IsReadOnly & SDB_ReadAccess)]
    lookup_field = "id"
    lookup_url_kwarg = "fleet_id"
    serializer_class = CylinderSerializer  # type: ignore[assignment]

    def get(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response | StreamingHttpResponse:
        """Export watchlist cylinders to Excel."""
        fleet = self.get_object()

        days_param = request.query_params.get("days", "60")
        try:
            days = int(days_param)
            if days < 0:
                days = 60
        except ValueError:
            days = 60

        cutoff_date = timezone.localdate() - timedelta(days=days)

        due_installs = (
            CylinderInstall.objects.filter(
                cylinder__fleet=fleet,
                status=InstallStatus.INSTALLED,
                install_date__lte=cutoff_date,
            )
            .select_related("cylinder", "project")
            .prefetch_related("cylinder__fleet")
            .order_by("install_date")
        )

        cylinder_ids = due_installs.values_list("cylinder_id", flat=True).distinct()

        cylinders = (
            Cylinder.objects.filter(id__in=cylinder_ids, fleet=fleet)
            .prefetch_related("installs")
            .order_by("-modified_date")
        )

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Watchlist")

        header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#4F46E5",
                "font_color": "white",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )

        cell_format = workbook.add_format({"border": 1, "valign": "top"})

        headers = [
            "Cylinder Name",
            "Serial",
            "Status",
            "Location",
            "Lat",
            "Long",
            "Install Date",
            "Modified Date",
        ]

        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, header_format)
            worksheet.set_column(col_num, col_num, max(len(header) + 2, 15))

        for row_num, cylinder in enumerate(cylinders, start=1):
            latest_install = cylinder.installs.filter(
                status=InstallStatus.INSTALLED
            ).first()

            row_data = [
                cylinder.name,
                cylinder.serial,
                cylinder.status.title(),
                latest_install.location_name if latest_install else "",
                float(latest_install.latitude) if latest_install else "",
                float(latest_install.longitude) if latest_install else "",
                latest_install.install_date.isoformat()
                if latest_install and latest_install.install_date
                else "",
                cylinder.modified_date.strftime("%Y-%m-%d %H:%M:%S"),
            ]

            for col_num, cell_value in enumerate(row_data):
                worksheet.write(row_num, col_num, cell_value, cell_format)

        workbook.close()
        output.seek(0)

        filename = (
            f"cylinder_fleet_watchlist_{fleet.name}_"
            f"{timezone.localdate().isoformat()}.xlsx"
        )
        filename = re.sub(r'[\\/*?:"<>|]', "", filename)

        response = StreamingHttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response


# ================== CYLINDER INSTALL API VIEWS ================== #


class CylinderInstallGeoJSONApiView(GenericAPIView[CylinderInstall], SDBAPIViewMixin):
    """
    GET: Get all installed cylinders the user has access to as GeoJSON.
    Returns cylinders from all fleets the user has at least read access to.
    """

    queryset = CylinderInstall.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CylinderInstallGeoJSONSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Return installed cylinders as GeoJSON FeatureCollection."""
        user = self.get_user()

        # Get all fleets the user has access to
        user_fleet_ids = CylinderFleetUserPermission.objects.filter(
            user=user,
            is_active=True,
        ).values_list("cylinder_fleet_id", flat=True)

        # Get all installed cylinders from those fleets
        installs = (
            CylinderInstall.objects.filter(
                status=InstallStatus.INSTALLED,
                cylinder__fleet_id__in=user_fleet_ids,
            )
            .select_related("cylinder", "cylinder__fleet", "project")
            .order_by("-install_date")
        )

        serializer = CylinderInstallGeoJSONSerializer(installs, many=True)
        return NoWrapResponse(FeatureCollection(serializer.data))  # type: ignore[no-untyped-call]


class CylinderInstallApiView(GenericAPIView[CylinderInstall], SDBAPIViewMixin):
    """
    GET: List all cylinder installs (optionally filter by cylinder_id or fleet_id)
    POST: Create a new cylinder install
    """

    queryset = CylinderInstall.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CylinderInstallSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        List cylinder installs.

        Query Parameters:
            cylinder_id (optional): Filter by cylinder UUID
            fleet_id (optional): Filter by fleet UUID
            status (optional): Filter by install status
        """
        user = self.get_user()

        # Get all fleets the user has access to
        user_fleet_ids = CylinderFleetUserPermission.objects.filter(
            user=user,
            is_active=True,
        ).values_list("cylinder_fleet_id", flat=True)

        # Start with base queryset - only installs from accessible fleets
        # Use prefetch_related for pressure_checks to avoid N+1 queries
        installs = (
            CylinderInstall.objects.filter(cylinder__fleet_id__in=user_fleet_ids)
            .select_related("cylinder", "cylinder__fleet", "project")
            .prefetch_related("pressure_checks")
        )

        # Apply optional filters
        cylinder_id = request.query_params.get("cylinder_id")
        if cylinder_id:
            installs = installs.filter(cylinder_id=cylinder_id)

        fleet_id = request.query_params.get("fleet_id")
        if fleet_id:
            installs = installs.filter(cylinder__fleet_id=UUID(fleet_id))

        status_filter = request.query_params.get("status")
        if status_filter:
            installs = installs.filter(status=status_filter)

        # Order by modified_date DESC
        installs = installs.order_by("-modified_date", "-install_date")

        serializer = CylinderInstallSerializer(installs, many=True)
        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new cylinder install."""
        user = self.get_user()

        data = request.data.copy()
        data["install_user"] = user.email
        data["created_by"] = user.email

        # Set default status if not provided
        if "status" not in data:
            data["status"] = InstallStatus.INSTALLED

        # Verify user has write access to the cylinder's fleet
        cylinder_id = data.get("cylinder")
        if cylinder_id:
            try:
                cylinder = Cylinder.objects.get(id=cylinder_id)
                has_write_access = CylinderFleetUserPermission.objects.filter(
                    user=user,
                    cylinder_fleet=cylinder.fleet,
                    is_active=True,
                    level__gte=PermissionLevel.READ_AND_WRITE,
                ).exists()
                if not has_write_access:
                    return ErrorResponse(
                        {
                            "error": (
                                "You do not have write access to this cylinder's fleet."
                            )
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
            except Cylinder.DoesNotExist:
                return ErrorResponse(
                    {"error": f"Cylinder with id '{cylinder_id}' does not exist."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        serializer = CylinderInstallSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class CylinderInstallSpecificApiView(GenericAPIView[CylinderInstall], SDBAPIViewMixin):
    """
    GET: Retrieve a specific cylinder install
    PATCH/PUT: Update cylinder install
    DELETE: Delete cylinder install (only if still INSTALLED)
    """

    # Use select_related and prefetch_related to avoid N+1 queries
    queryset = CylinderInstall.objects.select_related(
        "cylinder", "cylinder__fleet", "project"
    ).prefetch_related("pressure_checks")
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CylinderInstallSerializer
    lookup_field = "id"
    lookup_url_kwarg = "install_id"

    def _check_access(
        self, install: CylinderInstall, require_write: bool = False
    ) -> bool:
        """Check if user has access to this install's cylinder fleet."""
        user = self.get_user()
        min_level = (
            PermissionLevel.READ_AND_WRITE
            if require_write
            else PermissionLevel.READ_ONLY
        )
        return CylinderFleetUserPermission.objects.filter(
            user=user,
            cylinder_fleet=install.cylinder.fleet,
            is_active=True,
            level__gte=min_level,
        ).exists()

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Retrieve a specific cylinder install."""
        install = self.get_object()

        if not self._check_access(install):
            return ErrorResponse(
                {"error": "You do not have access to this cylinder install."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(install)
        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        """Update a cylinder install."""
        user = self.get_user()
        install = self.get_object()

        if not self._check_access(install, require_write=True):
            return ErrorResponse(
                {"error": "You do not have write access to this cylinder install."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data.copy()

        # If changing status to anything other than INSTALLED, set uninstall fields
        new_status = data.get("status", install.status)
        if new_status != InstallStatus.INSTALLED:
            if "uninstall_user" not in data or not data["uninstall_user"]:
                data["uninstall_user"] = user.email
            if "uninstall_date" not in data or not data["uninstall_date"]:
                data["uninstall_date"] = timezone.localdate().isoformat()

        serializer = self.get_serializer(install, data=data, partial=partial)

        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Full update of cylinder install."""
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Partial update of cylinder install."""
        return self._modify_obj(request=request, partial=True, **kwargs)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete a cylinder install."""
        install = self.get_object()

        if not self._check_access(install, require_write=True):
            return ErrorResponse(
                {"error": "You do not have write access to this cylinder install."},
                status=status.HTTP_403_FORBIDDEN,
            )

        install_id = install.id
        install.delete()

        return SuccessResponse(
            {"id": str(install_id), "message": "Cylinder install deleted successfully"}
        )


# ================== CYLINDER PRESSURE CHECK API VIEWS ================== #


class CylinderPressureCheckApiView(
    GenericAPIView[CylinderPressureCheck], SDBAPIViewMixin
):
    """
    GET: List all pressure checks for a cylinder install
    POST: Create a new pressure check
    """

    queryset = CylinderPressureCheck.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CylinderPressureCheckSerializer

    def _get_install_and_check_access(
        self, install_id: str, require_write: bool = False
    ) -> tuple[CylinderInstall | None, Response | None]:
        """Get install and check user access. Returns (install, error_response)."""
        user = self.get_user()

        try:
            install = CylinderInstall.objects.select_related(
                "cylinder", "cylinder__fleet"
            ).get(id=install_id)
        except CylinderInstall.DoesNotExist:
            return None, ErrorResponse(
                {"error": f"Cylinder install with id '{install_id}' does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        min_level = (
            PermissionLevel.READ_AND_WRITE
            if require_write
            else PermissionLevel.READ_ONLY
        )
        has_access = CylinderFleetUserPermission.objects.filter(
            user=user,
            cylinder_fleet=install.cylinder.fleet,
            is_active=True,
            level__gte=min_level,
        ).exists()

        if not has_access:
            return None, ErrorResponse(
                {"error": "You do not have access to this cylinder install."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return install, None

    def get(
        self, request: Request, install_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """List pressure checks for a cylinder install."""
        install, error = self._get_install_and_check_access(install_id)
        if error:
            return error

        checks = CylinderPressureCheck.objects.filter(install=install).order_by(
            "-creation_date"
        )

        serializer = CylinderPressureCheckSerializer(checks, many=True)
        return SuccessResponse(serializer.data)

    def post(
        self, request: Request, install_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """Create a new pressure check."""
        user = self.get_user()
        install, error = self._get_install_and_check_access(
            install_id, require_write=True
        )
        if error:
            return error

        data = request.data.copy()
        data["install"] = install.id  # type: ignore[union-attr]
        data["user"] = user.email

        serializer = CylinderPressureCheckSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class CylinderPressureCheckSpecificApiView(
    GenericAPIView[CylinderPressureCheck], SDBAPIViewMixin
):
    """
    GET: Retrieve a specific pressure check
    PATCH/PUT: Update pressure check
    DELETE: Delete pressure check
    """

    # Use select_related to avoid N+1 queries when checking access
    queryset = CylinderPressureCheck.objects.select_related(
        "install", "install__cylinder", "install__cylinder__fleet"
    )
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CylinderPressureCheckSerializer
    lookup_field = "id"
    lookup_url_kwarg = "check_id"

    def _check_access(
        self, check: CylinderPressureCheck, require_write: bool = False
    ) -> bool:
        """Check if user has access to this pressure check."""
        user = self.get_user()
        min_level = (
            PermissionLevel.READ_AND_WRITE
            if require_write
            else PermissionLevel.READ_ONLY
        )
        return CylinderFleetUserPermission.objects.filter(
            user=user,
            cylinder_fleet=check.install.cylinder.fleet,
            is_active=True,
            level__gte=min_level,
        ).exists()

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Retrieve a specific pressure check."""
        check = self.get_object()

        if not self._check_access(check):
            return ErrorResponse(
                {"error": "You do not have access to this pressure check."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(check)
        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        """Update a pressure check."""
        check = self.get_object()

        if not self._check_access(check, require_write=True):
            return ErrorResponse(
                {"error": "You do not have write access to this pressure check."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Inject install from existing object (not changeable via API)
        data = request.data.copy()
        data["install"] = check.install_id

        serializer = self.get_serializer(check, data=data, partial=partial)

        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Full update of pressure check."""
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Partial update of pressure check."""
        return self._modify_obj(request=request, partial=True, **kwargs)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete a pressure check."""
        check = self.get_object()

        if not self._check_access(check, require_write=True):
            return ErrorResponse(
                {"error": "You do not have write access to this pressure check."},
                status=status.HTTP_403_FORBIDDEN,
            )

        check_id = check.id
        check.delete()

        return SuccessResponse(
            {"id": str(check_id), "message": "Pressure check deleted successfully"}
        )
