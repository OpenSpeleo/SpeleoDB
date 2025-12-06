# -*- coding: utf-8 -*-

from __future__ import annotations

import io
import logging
import re
from typing import TYPE_CHECKING
from typing import Any

import xlsxwriter
import xlsxwriter.format
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django.db.models import Case
from django.db.models import Count
from django.db.models import OuterRef
from django.db.models import Prefetch
from django.db.models import Q
from django.db.models import QuerySet
from django.db.models import Subquery
from django.db.models import Value
from django.db.models import When
from django.db.models.functions import Least
from django.http import Http404
from django.http import StreamingHttpResponse
from django.utils import timezone
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
from speleodb.api.v1.serializers import SensorFleetListSerializer
from speleodb.api.v1.serializers import SensorFleetSerializer
from speleodb.api.v1.serializers import SensorFleetUserPermissionSerializer
from speleodb.api.v1.serializers import SensorInstallSerializer
from speleodb.api.v1.serializers import SensorSerializer
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Sensor
from speleodb.gis.models import SensorFleet
from speleodb.gis.models import SensorFleetUserPermission
from speleodb.gis.models import SensorInstall
from speleodb.gis.models import SensorStatus
from speleodb.gis.models import Station
from speleodb.gis.models import SubSurfaceStation
from speleodb.gis.models.sensor import InstallStatus
from speleodb.users.models import User
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.exceptions import BadRequestError
from speleodb.utils.exceptions import NotAuthorizedError
from speleodb.utils.exceptions import UserNotActiveError
from speleodb.utils.exceptions import UserNotFoundError
from speleodb.utils.exceptions import ValueNotFoundError
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response

logger = logging.getLogger(__name__)


class SensorFleetApiView(GenericAPIView[SensorFleet], SDBAPIViewMixin):
    """
    GET: List all sensor fleets accessible to the authenticated user
    POST: Create a new sensor fleet
    """

    queryset = SensorFleet.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SensorFleetSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List all sensor fleets with user permissions."""
        user = self.get_user()

        # Get all active fleets user has access to with sensor count
        fleet_perms: QuerySet[SensorFleetUserPermission] = (
            SensorFleetUserPermission.objects.filter(
                user=user,
                is_active=True,
                sensor_fleet__is_active=True,
            )
            .select_related("sensor_fleet")
            .annotate(sensor_count=Count("sensor_fleet__sensors"))
        )

        # Build response data with permission info
        fleets_data = []
        for perm in fleet_perms:
            fleet = perm.sensor_fleet
            # Use list serializer for optimized response
            serializer = SensorFleetListSerializer(fleet)
            fleet_data = serializer.data
            fleet_data["sensor_count"] = perm.sensor_count  # type: ignore[attr-defined]
            fleet_data["user_permission_level"] = perm.level
            fleet_data["user_permission_level_label"] = perm.level_label
            fleets_data.append(fleet_data)

        return SuccessResponse(fleets_data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new sensor fleet."""
        user = self.get_user()

        data = request.data.copy()

        # Extract sensors data if provided
        sensors_data = data.pop("sensors", [])

        # Add created_by to data
        data["created_by"] = user.email

        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()

        for sensor_data in sensors_data:
            sensor_serializer = SensorSerializer(data=sensor_data)
            if sensor_serializer.is_valid():
                _ = sensor_serializer.save(fleet=serializer.instance)

            else:
                return ErrorResponse(
                    {"errors": sensor_serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)


class SensorFleetSpecificApiView(GenericAPIView[SensorFleet], SDBAPIViewMixin):
    """
    GET: Retrieve a specific sensor fleet
    PUT/PATCH: Update a sensor fleet
    DELETE: Deactivate a sensor fleet
    """

    queryset = SensorFleet.objects.all()
    permission_classes = [
        (IsObjectDeletion & SDB_AdminAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = SensorFleetSerializer
    lookup_field = "id"
    lookup_url_kwarg = "fleet_id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Retrieve a specific sensor fleet."""
        sensor_fleet = self.get_object()
        serializer = self.get_serializer(sensor_fleet)
        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        """Update a sensor fleet."""
        sensor_fleet = self.get_object()
        serializer = self.get_serializer(
            sensor_fleet, data=request.data, partial=partial
        )

        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Full update of sensor fleet."""
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Partial update of sensor fleet."""
        return self._modify_obj(request=request, partial=True, **kwargs)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Deactivate a sensor fleet instead of deleting it.

        Sets is_active=False to deactivate the fleet while preserving
        all data. Also deactivates all user permissions for the fleet.
        """
        user = self.get_user()
        sensor_fleet = self.get_object()

        # Deactivate all permissions
        for perm in sensor_fleet.user_permissions.all():
            perm.deactivate(deactivated_by=user)

        # Deactivate the fleet
        sensor_fleet.is_active = False
        sensor_fleet.save()

        return SuccessResponse(
            {"id": str(sensor_fleet.id), "message": "Sensor fleet deleted successfully"}
        )


class SensorApiView(GenericAPIView[SensorFleet], SDBAPIViewMixin):
    """
    GET: List all sensors in a fleet
    POST: Create a new sensor in a fleet
    """

    queryset = SensorFleet.objects.all()
    permission_classes = [
        (IsObjectCreation & SDB_WriteAccess) | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = SensorFleetSerializer
    lookup_field = "id"
    lookup_url_kwarg = "fleet_id"

    def get(
        self, request: Request, fleet_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """List all sensors in a fleet."""
        fleet = self.get_object()

        sensors = Sensor.objects.filter(fleet=fleet).order_by("name")
        serializer = SensorSerializer(sensors, many=True)
        return SuccessResponse(serializer.data)

    def post(
        self, request: Request, fleet_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """Create a new sensor in a fleet."""
        user = self.get_user()
        fleet = self.get_object()

        # Add fleet and created_by to data
        data = request.data.copy()

        data["fleet"] = fleet.id
        data["created_by"] = user.email

        # Pass fleet_id in context for validation
        serializer = SensorSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class SensorSpecificApiView(GenericAPIView[Sensor], SDBAPIViewMixin):
    """
    GET: Retrieve a specific sensor
    PUT/PATCH: Update a sensor
    DELETE: Delete a sensor
    """

    queryset = Sensor.objects.all()
    permission_classes = [
        (IsObjectDeletion & SDB_WriteAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = SensorSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Retrieve a specific sensor."""
        sensor = self.get_object()
        serializer = self.get_serializer(sensor)
        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        """Update a sensor."""
        sensor = self.get_object()
        serializer = self.get_serializer(sensor, data=request.data, partial=partial)

        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Full update of sensor."""
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Partial update of sensor."""
        return self._modify_obj(request=request, partial=True, **kwargs)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete a sensor permanently."""
        sensor = self.get_object()
        sensor_id = sensor.id
        sensor.delete()

        return SuccessResponse(
            {"id": str(sensor_id), "message": "Sensor deleted successfully"}
        )


class SensorToggleFunctionalApiView(GenericAPIView[Sensor], SDBAPIViewMixin):
    """
    PATCH: Toggle sensor functional status
    """

    queryset = Sensor.objects.all()
    permission_classes = [SDB_WriteAccess]
    serializer_class = SensorSerializer
    lookup_field = "id"

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Toggle the sensor status."""
        sensor = self.get_object()

        if sensor.status == SensorStatus.FUNCTIONAL:
            sensor.status = SensorStatus.BROKEN
        else:
            sensor.status = SensorStatus.FUNCTIONAL

        sensor.save()

        serializer = self.get_serializer(sensor)
        return SuccessResponse(serializer.data)


class SensorFleetPermissionApiView(GenericAPIView[SensorFleet], SDBAPIViewMixin):
    """
    GET: List all permissions for a fleet
    POST: Grant permission to a user
    """

    queryset = SensorFleet.objects.all()
    permission_classes = [SDB_AdminAccess | (IsReadOnly & SDB_ReadAccess)]
    serializer_class = SensorFleetSerializer
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
                            # This by default make no sense because you need to be
                            # sensor fleet admin to create permission. So you obviously
                            # can't create permission for yourself. Added just as
                            # safety and logical consistency.
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

        permissions = SensorFleetUserPermission.objects.filter(
            sensor_fleet=fleet,
            is_active=True,
        ).select_related("user")

        serializer = SensorFleetUserPermissionSerializer(permissions, many=True)
        return SuccessResponse(serializer.data)

    def post(
        self, request: Request, fleet_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """Grant permission to a user (requires ADMIN access)."""
        fleet = self.get_object()

        perm_data = self._process_request_data(request=request, data=request.data)

        target_user: User = perm_data["user"]
        permission, created = SensorFleetUserPermission.objects.get_or_create(
            user=target_user,
            sensor_fleet=fleet,
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

            # Reactivate permission
            permission.reactivate(level=perm_data["level"])

        else:
            # Now assign the role. Couldn't do it during object creation because
            # of the use of `get_or_create`
            permission.level = perm_data["level"]

        permission.save()

        permission_serializer = SensorFleetUserPermissionSerializer(permission)
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

        # Can't edit your own permission
        if user == perm_data["user"]:
            return ErrorResponse(
                {"error": ("A user can not edit their own permission")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_user: User = perm_data["user"]
        try:
            permission = SensorFleetUserPermission.objects.get(
                user=target_user,
                sensor_fleet=fleet,
            )

        except ObjectDoesNotExist as e:
            raise Http404(
                f"A permission for this user: `{target_user}` does not exist."
            ) from e

        permission.level = perm_data["level"]
        permission.save()

        permission_serializer = SensorFleetUserPermissionSerializer(permission)
        fleet_serializer = self.get_serializer(fleet)

        # Refresh the `modified_date` field
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

        # Can't edit your own permission
        if user == perm_data["user"]:
            return ErrorResponse(
                {"error": ("A user can not edit their own permission")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_user: User = perm_data["user"]
        try:
            permission = SensorFleetUserPermission.objects.get(
                sensor_fleet=fleet,
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


class SensorFleetExportExcelApiView(GenericAPIView[SensorFleet], SDBAPIViewMixin):
    """
    Export sensor fleet sensors to Excel format.

    GET: Download Excel file containing all sensors in a fleet.
    """

    queryset = SensorFleet.objects.all()
    permission_classes = [(IsReadOnly & SDB_ReadAccess)]
    lookup_field = "id"
    lookup_url_kwarg = "fleet_id"
    serializer_class = SensorSerializer  # type: ignore[assignment]

    def get(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response | StreamingHttpResponse:
        """Export fleet sensors to Excel."""
        fleet = self.get_object()

        # Get all sensors for this fleet
        sensors = (
            Sensor.objects.filter(fleet=fleet)
            .prefetch_related("installs", "installs__station")
            .order_by("-modified_date")
        )

        # Create Excel file in memory
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Sensors")

        # Define formats
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

        # Define headers
        headers = [
            "Sensor Name",
            "Status",
            "Notes",
            "Current Project",
            "Current Lat",
            "Current Long",
            "Memory Expiry",
            "Battery Expiry",
            "Modified Date",
        ]

        # Write headers
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, header_format)
            # Auto-adjust column width based on header length
            worksheet.set_column(col_num, col_num, max(len(header) + 2, 15))

        # Write data rows
        for row_num, sensor in enumerate(sensors, start=1):
            # Get latest install info
            latest_install = sensor.installs.filter(
                status=InstallStatus.INSTALLED
            ).first()

            project_name = (
                station.project.name
                if (
                    latest_install is not None
                    and isinstance(station := latest_install.station, SubSurfaceStation)
                )
                else ""
            )

            lat = float(latest_install.station.latitude) if latest_install else ""
            long = float(latest_install.station.longitude) if latest_install else ""
            mem_expiry = (
                latest_install.expiracy_memory_date.strftime("%Y-%m-%d")
                if latest_install and latest_install.expiracy_memory_date
                else ""
            )
            bat_expiry = (
                latest_install.expiracy_battery_date.strftime("%Y-%m-%d")
                if latest_install and latest_install.expiracy_battery_date
                else ""
            )

            row_data = [
                sensor.name,
                sensor.status.title(),
                sensor.notes,
                project_name,
                lat,
                long,
                mem_expiry,
                bat_expiry,
                sensor.modified_date.strftime("%Y-%m-%d %H:%M:%S"),
            ]

            for col_num, cell_value in enumerate(row_data):
                worksheet.write(row_num, col_num, cell_value, cell_format)

        workbook.close()
        output.seek(0)

        filename = f"sensor_fleet_{fleet.name}_{timezone.localdate().isoformat()}.xlsx"

        # Sanitize filename
        filename = re.sub(r'[\\/*?:"<>|]', "", filename)

        response = StreamingHttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response


class SensorFleetWatchlistApiView(GenericAPIView[SensorFleet], SDBAPIViewMixin):
    """
    GET: List sensors in a fleet that are due for retrieval.

    Query Parameters:
        days (optional): Number of days to look ahead for expiry (default: 60).
                         Returns sensors with expiry dates within the next N days.
    """

    queryset = SensorFleet.objects.all()
    permission_classes = [(IsReadOnly & SDB_ReadAccess)]
    serializer_class = SensorSerializer  # type: ignore[assignment]
    lookup_field = "id"
    lookup_url_kwarg = "fleet_id"

    def get(
        self, request: Request, fleet_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """List sensors in a fleet that are due for retrieval."""
        fleet = self.get_object()

        # Get days parameter from query string, default to 60 (2 months)
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

        # Get installs due for retrieval for sensors in this fleet
        due_installs = (
            SensorInstall.objects.due_for_retrieval(days=days)  # pyright: ignore[reportAttributeAccessIssue]
            .filter(sensor__fleet=fleet)
            .select_related("sensor", "station")
            .prefetch_related("sensor__fleet")
        )

        # Get unique sensors from the installs
        sensor_ids = due_installs.values_list("sensor_id", flat=True).distinct()

        # Annotate sensors with minimum expiry date from their active installs
        # Use subquery to get the minimum of memory and battery expiry dates
        active_installs = SensorInstall.objects.filter(
            sensor=OuterRef("pk"), status=InstallStatus.INSTALLED
        )

        # Annotate with minimum expiry date (least of memory and battery)
        # Handle NULL values: if one is NULL, use the other; if both NULL, use NULL
        # Use Case/When to handle NULLs properly
        sensors = (
            Sensor.objects.filter(id__in=sensor_ids, fleet=fleet)
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
                    ).select_related("station"),
                    to_attr="active_installs",
                )
            )
            .order_by("min_expiry_date", "-modified_date")
        )

        serializer = SensorSerializer(sensors, many=True)
        return SuccessResponse(serializer.data)


class SensorFleetWatchlistExportExcelApiView(
    GenericAPIView[SensorFleet], SDBAPIViewMixin
):
    """
    Export watchlist sensors to Excel format.

    GET: Download Excel file containing sensors due for retrieval.
    Query Parameters:
        days (optional): Number of days to look ahead for expiry (default: 60).
    """

    queryset = SensorFleet.objects.all()
    permission_classes = [(IsReadOnly & SDB_ReadAccess)]
    lookup_field = "id"
    lookup_url_kwarg = "fleet_id"
    serializer_class = SensorSerializer  # type: ignore[assignment]

    def get(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response | StreamingHttpResponse:
        """Export watchlist sensors to Excel."""
        fleet = self.get_object()

        # Get days parameter from query string, default to 60 (2 months)
        days_param = request.query_params.get("days", "60")
        try:
            days = int(days_param)
            if days < 0:
                days = 60
        except ValueError:
            days = 60

        # Get installs due for retrieval for sensors in this fleet
        due_installs = (
            SensorInstall.objects.due_for_retrieval(days=days)  # pyright: ignore[reportAttributeAccessIssue]
            .filter(sensor__fleet=fleet)
            .select_related("sensor", "station")
            .prefetch_related("sensor__fleet")
        )

        # Get unique sensors from the installs
        sensor_ids = due_installs.values_list("sensor_id", flat=True).distinct()

        # Annotate sensors with minimum expiry date for sorting
        active_installs = SensorInstall.objects.filter(
            sensor=OuterRef("pk"), status=InstallStatus.INSTALLED
        )

        sensors = (
            Sensor.objects.filter(id__in=sensor_ids, fleet=fleet)
            .annotate(
                min_expiry_date=Subquery(
                    active_installs.annotate(
                        min_expiry=Case(
                            When(
                                Q(expiracy_memory_date__isnull=False)
                                & Q(expiracy_battery_date__isnull=False),
                                then=Least(
                                    "expiracy_memory_date", "expiracy_battery_date"
                                ),
                            ),
                            When(
                                Q(expiracy_memory_date__isnull=False)
                                & Q(expiracy_battery_date__isnull=True),
                                then="expiracy_memory_date",
                            ),
                            When(
                                Q(expiracy_memory_date__isnull=True)
                                & Q(expiracy_battery_date__isnull=False),
                                then="expiracy_battery_date",
                            ),
                            default=Value(None),
                        )
                    ).values("min_expiry")[:1]
                )
            )
            .prefetch_related("installs", "installs__station")
            .order_by("min_expiry_date", "-modified_date")
        )

        # Create Excel file in memory
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Watchlist")

        # Define formats
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

        # Define headers
        headers = [
            "Sensor Name",
            "Status",
            "Notes",
            "Current Project",
            "Current Lat",
            "Current Long",
            "Memory Expiry",
            "Battery Expiry",
            "Modified Date",
        ]

        # Write headers
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, header_format)
            worksheet.set_column(col_num, col_num, max(len(header) + 2, 15))

        # Write data rows
        for row_num, sensor in enumerate(sensors, start=1):
            latest_install = sensor.installs.filter(
                status=InstallStatus.INSTALLED
            ).first()

            project_name = (
                station.project.name
                if (
                    latest_install is not None
                    and isinstance(station := latest_install.station, SubSurfaceStation)
                )
                else ""
            )

            lat = float(latest_install.station.latitude) if latest_install else ""
            long = float(latest_install.station.longitude) if latest_install else ""
            mem_expiry = (
                latest_install.expiracy_memory_date.strftime("%Y-%m-%d")
                if latest_install and latest_install.expiracy_memory_date
                else ""
            )
            bat_expiry = (
                latest_install.expiracy_battery_date.strftime("%Y-%m-%d")
                if latest_install and latest_install.expiracy_battery_date
                else ""
            )

            row_data = [
                sensor.name,
                sensor.status.title(),
                sensor.notes,
                project_name,
                lat,
                long,
                mem_expiry,
                bat_expiry,
                sensor.modified_date.strftime("%Y-%m-%d %H:%M:%S"),
            ]

            for col_num, cell_value in enumerate(row_data):
                worksheet.write(row_num, col_num, cell_value, cell_format)

        workbook.close()
        output.seek(0)

        filename = (
            f"sensor_fleet_watchlist_{fleet.name}_"
            f"{timezone.localdate().isoformat()}.xlsx"
        )

        filename = re.sub(r'[\\/*?:"<>|]', "", filename)

        response = StreamingHttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response


class StationSensorInstallApiView(GenericAPIView[Station], SDBAPIViewMixin):
    """
    GET: List all sensor installs for a station
    POST: Create a new sensor install (install sensor at station)
    """

    queryset = Station.objects.all()
    permission_classes = [SDB_WriteAccess | (IsReadOnly & SDB_ReadAccess)]
    lookup_field = "id"

    def get_serializer_class(self) -> type[SensorInstallSerializer]:  # type: ignore[override]
        """Return the serializer class for sensor installs."""
        return SensorInstallSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        List sensor installs for a station.

        Query Parameters:
            status (optional): Filter by install status
                              (installed, retrieved, lost, abandoned).
                              If not provided, returns all installs.
        """
        station = self.get_object()

        # Start with base queryset
        installs = SensorInstall.objects.filter(station=station)

        # Apply optional status filter
        status_filter = request.query_params.get("status")
        if status_filter:
            installs = installs.filter(status=status_filter)

        # Order by modified_date DESC, then install_date DESC
        installs = installs.order_by("-modified_date", "-install_date")

        serializer = SensorInstallSerializer(installs, many=True)
        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new sensor install."""
        user = self.get_user()
        station = self.get_object()

        data = request.data.copy()
        data["station"] = station.id
        data["install_user"] = user.email
        data["created_by"] = user.email

        # Set default status if not provided
        if "status" not in data:
            data["status"] = InstallStatus.INSTALLED

        serializer = SensorInstallSerializer(data=data)
        if serializer.is_valid():
            try:
                serializer.save()
                return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_dict: dict[str, Any] = {}
                if hasattr(e, "error_dict"):
                    error_dict = e.error_dict
                elif hasattr(e, "error_list"):
                    error_dict = {"non_field_errors": e.error_list}
                else:
                    error_dict = {"non_field_errors": [str(e)]}
                return ErrorResponse(
                    {"errors": error_dict},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class StationSensorInstallSpecificApiView(
    GenericAPIView[SensorInstall], SDBAPIViewMixin
):
    """
    GET: Retrieve a specific sensor install
    PATCH: Update sensor install status (Retrieved/Lost/Abandoned)
    """

    queryset = SensorInstall.objects.all()
    permission_classes = [SDB_WriteAccess | (IsReadOnly & SDB_ReadAccess)]
    serializer_class = SensorInstallSerializer
    lookup_field = "id"
    lookup_url_kwarg = "install_id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Retrieve a specific sensor install."""
        sensor_install = self.get_object()
        serializer = self.get_serializer(sensor_install)
        return SuccessResponse(serializer.data)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Update sensor install status."""
        user = self.get_user()
        sensor_install = self.get_object()

        data = request.data.copy()

        # If changing status to anything else than RETRIEVED:
        # => set uninstall_user if not provided
        new_status = data.get("status", sensor_install.status)
        if new_status != InstallStatus.INSTALLED:
            if "uninstall_user" not in data or not data["uninstall_user"]:
                data["uninstall_user"] = user.email
            if "uninstall_date" not in data or not data["uninstall_date"]:
                data["uninstall_date"] = timezone.localdate().isoformat()

        serializer = self.get_serializer(sensor_install, data=data, partial=True)

        if serializer.is_valid():
            try:
                serializer.save()

                match new_status:
                    case InstallStatus.LOST:
                        sensor_install.sensor.status = SensorStatus.LOST
                        sensor_install.sensor.save()
                    case InstallStatus.ABANDONED:
                        sensor_install.sensor.status = SensorStatus.ABANDONED
                        sensor_install.sensor.save()
                    case _:
                        pass
                return SuccessResponse(serializer.data)

            except ValidationError as e:
                error_dict: dict[str, Any] = {}
                if hasattr(e, "error_dict"):
                    error_dict = e.error_dict
                elif hasattr(e, "error_list"):
                    error_dict = {"non_field_errors": e.error_list}
                else:
                    error_dict = {"non_field_errors": [str(e)]}
                return ErrorResponse(
                    {"errors": error_dict},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class StationSensorInstallExportExcelApiView(GenericAPIView[Station], SDBAPIViewMixin):
    """
    Export sensor installation history to Excel format.

    GET: Download Excel file containing all sensor installs for a station.
    """

    queryset = Station.objects.all()
    permission_classes = [SDB_WriteAccess | (IsReadOnly & SDB_ReadAccess)]
    lookup_field = "id"
    serializer_class = SensorInstallSerializer  # type: ignore[assignment]

    def get(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response | StreamingHttpResponse:
        """Export sensor installs to Excel."""
        station = self.get_object()

        # Get all sensor installs for this station
        installs = (
            SensorInstall.objects.filter(station=station)
            .select_related("sensor", "sensor__fleet", "station")
            .order_by("-modified_date", "-install_date")
        )

        # Create Excel file in memory
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Sensor Install History")

        # Define formats
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

        # Status-specific formats with colors
        status_formats: dict[InstallStatus, xlsxwriter.format.Format] = {
            InstallStatus.INSTALLED: workbook.add_format(
                {
                    "border": 1,
                    "valign": "top",
                    "bg_color": "#10B981",
                    "font_color": "white",
                }
            ),
            InstallStatus.RETRIEVED: workbook.add_format(
                {
                    "border": 1,
                    "valign": "top",
                    "bg_color": "#3B82F6",
                    "font_color": "white",
                }
            ),
            InstallStatus.LOST: workbook.add_format(
                {
                    "border": 1,
                    "valign": "top",
                    "bg_color": "#F59E0B",
                    "font_color": "white",
                }
            ),
            InstallStatus.ABANDONED: workbook.add_format(
                {
                    "border": 1,
                    "valign": "top",
                    "bg_color": "#EF4444",
                    "font_color": "white",
                }
            ),
        }

        # Define headers
        headers = [
            "Sensor Name",
            "Sensor Fleet Name",
            "State",
            "Install Date",
            "Install User",
            "Retrieval Date",
            "Retrieval User",
            "Memory Expiry Date",
            "Battery Expiry Date",
            "Created Date",
            "Modified Date",
        ]

        # Write headers
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, header_format)
            # Auto-adjust column width based on header length
            worksheet.set_column(col_num, col_num, max(len(header) + 2, 15))

        # Write data rows
        row_num = 1
        for install in installs:
            col_num = 0

            # Sensor Name
            worksheet.write(
                row_num, col_num, install.sensor.name or "Unknown", cell_format
            )
            col_num += 1

            # Sensor Fleet Name
            worksheet.write(
                row_num,
                col_num,
                install.sensor.fleet.name if install.sensor.fleet else "Unknown",
                cell_format,
            )
            col_num += 1

            # Status (with colored formatting)
            install_status: InstallStatus = install.status  # type: ignore[assignment]
            status_format = status_formats.get(install_status, cell_format)
            worksheet.write(
                row_num, col_num, install.get_status_display(), status_format
            )  # pyright: ignore[reportAttributeAccessIssue]
            col_num += 1

            # Install Date
            if install.install_date:
                worksheet.write(
                    row_num, col_num, install.install_date.isoformat(), cell_format
                )
            else:
                worksheet.write(row_num, col_num, "", cell_format)
            col_num += 1

            # Install User
            worksheet.write(row_num, col_num, install.install_user or "", cell_format)
            col_num += 1

            # Retrieval Date
            if install.uninstall_date:
                worksheet.write(
                    row_num, col_num, install.uninstall_date.isoformat(), cell_format
                )
            else:
                worksheet.write(row_num, col_num, "", cell_format)
            col_num += 1

            # Retrieval User
            worksheet.write(row_num, col_num, install.uninstall_user or "", cell_format)
            col_num += 1

            # Memory Expiry Date
            if install.expiracy_memory_date:
                worksheet.write(
                    row_num,
                    col_num,
                    install.expiracy_memory_date.isoformat(),
                    cell_format,
                )
            else:
                worksheet.write(row_num, col_num, "", cell_format)
            col_num += 1

            # Battery Expiry Date
            if install.expiracy_battery_date:
                worksheet.write(
                    row_num,
                    col_num,
                    install.expiracy_battery_date.isoformat(),
                    cell_format,
                )
            else:
                worksheet.write(row_num, col_num, "", cell_format)
            col_num += 1

            # Created Date
            if install.creation_date:
                worksheet.write(
                    row_num,
                    col_num,
                    install.creation_date.strftime("%Y-%m-%d %H:%M:%S"),
                    cell_format,
                )
            else:
                worksheet.write(row_num, col_num, "", cell_format)
            col_num += 1

            # Modified Date
            if install.modified_date:
                worksheet.write(
                    row_num,
                    col_num,
                    install.modified_date.strftime("%Y-%m-%d %H:%M:%S"),
                    cell_format,
                )
            else:
                worksheet.write(row_num, col_num, "", cell_format)
            col_num += 1

            row_num += 1

        # Close workbook
        workbook.close()
        output.seek(0)

        # Generate filename with timestamp
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize station name for filename (remove special characters)
        station_name = re.sub(r"[^\w\s-]", "", station.name).strip()
        station_name = re.sub(r"[-\s]+", "_", station_name)
        filename = f"station_{station_name}_sensor_history_{timestamp}.xlsx"

        return StreamingHttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
