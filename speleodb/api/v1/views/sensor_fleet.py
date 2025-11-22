# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from django.http import Http404
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import IsObjectCreation
from speleodb.api.v1.permissions import IsObjectDeletion
from speleodb.api.v1.permissions import IsObjectEdition
from speleodb.api.v1.permissions import IsReadOnly
from speleodb.api.v1.permissions import SensorFleetUserHasAdminAccess
from speleodb.api.v1.permissions import SensorFleetUserHasReadAccess
from speleodb.api.v1.permissions import SensorFleetUserHasWriteAccess
from speleodb.api.v1.serializers import SensorFleetListSerializer
from speleodb.api.v1.serializers import SensorFleetSerializer
from speleodb.api.v1.serializers import SensorFleetUserPermissionSerializer
from speleodb.api.v1.serializers import SensorSerializer
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Sensor
from speleodb.gis.models import SensorFleet
from speleodb.gis.models import SensorFleetUserPermission
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
        fleet_perms = (
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
            fleet_data["sensor_count"] = perm.sensor_count
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
        (IsObjectDeletion & SensorFleetUserHasAdminAccess)
        | (IsObjectEdition & SensorFleetUserHasWriteAccess)
        | (IsReadOnly & SensorFleetUserHasReadAccess)
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
        for perm in sensor_fleet.rel_user_permissions.all():
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
        (IsObjectCreation & SensorFleetUserHasWriteAccess)
        | (IsReadOnly & SensorFleetUserHasReadAccess)
    ]
    serializer_class = SensorFleetSerializer
    lookup_field = "id"
    lookup_url_kwarg = "fleet_id"

    def get(
        self, request: Request, fleet_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """List all sensors in a fleet."""
        fleet = self.get_object()

        sensors = Sensor.objects.filter(fleet=fleet).order_by("-modified_date")
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
        (IsObjectDeletion & SensorFleetUserHasWriteAccess)
        | (IsObjectEdition & SensorFleetUserHasWriteAccess)
        | (IsReadOnly & SensorFleetUserHasReadAccess)
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
    permission_classes = [SensorFleetUserHasWriteAccess]
    serializer_class = SensorSerializer
    lookup_field = "id"

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Toggle the is_functional status of a sensor."""
        sensor = self.get_object()

        # Toggle the functional status
        sensor.is_functional = not sensor.is_functional
        sensor.save()

        serializer = self.get_serializer(sensor)
        return SuccessResponse(serializer.data)


class SensorFleetPermissionApiView(GenericAPIView[SensorFleet], SDBAPIViewMixin):
    """
    GET: List all permissions for a fleet
    POST: Grant permission to a user
    """

    queryset = SensorFleet.objects.all()
    permission_classes = [
        SensorFleetUserHasAdminAccess | (IsReadOnly & SensorFleetUserHasReadAccess)
    ]
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
