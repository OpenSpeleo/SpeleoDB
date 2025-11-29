# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import IsObjectDeletion
from speleodb.api.v1.permissions import IsObjectEdition
from speleodb.api.v1.permissions import IsReadOnly
from speleodb.api.v1.permissions import SDB_AdminAccess
from speleodb.api.v1.permissions import SDB_ReadAccess
from speleodb.api.v1.permissions import SDB_WriteAccess
from speleodb.api.v1.serializers.surface_network import (
    SurfaceMonitoringNetworkListSerializer,
)
from speleodb.api.v1.serializers.surface_network import (
    SurfaceMonitoringNetworkSerializer,
)
from speleodb.api.v1.serializers.surface_network import (
    SurfaceMonitoringNetworkUserPermissionSerializer,
)
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import SurfaceMonitoringNetwork
from speleodb.gis.models import SurfaceMonitoringNetworkUserPermission
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


class SurfaceMonitoringNetworkApiView(
    GenericAPIView[SurfaceMonitoringNetwork], SDBAPIViewMixin
):
    """
    GET: List all networks accessible to the authenticated user
    POST: Create a new network
    """

    queryset = SurfaceMonitoringNetwork.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SurfaceMonitoringNetworkSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List all networks with user permissions."""
        user = self.get_user()

        # Get all active networks user has access to
        network_perms = SurfaceMonitoringNetworkUserPermission.objects.filter(
            user=user,
            is_active=True,
            network__is_active=True,
        ).select_related("network")

        # Build response data with permission info
        networks_data = []
        for perm in network_perms:
            network = perm.network
            # Use list serializer for optimized response
            serializer = SurfaceMonitoringNetworkListSerializer(network)
            network_data = serializer.data
            network_data["user_permission_level"] = perm.level
            network_data["user_permission_level_label"] = perm.level_label
            networks_data.append(network_data)

        return SuccessResponse(networks_data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new network."""
        user = self.get_user()

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save(created_by=user.email)

        return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)


class SurfaceMonitoringNetworkSpecificApiView(
    GenericAPIView[SurfaceMonitoringNetwork], SDBAPIViewMixin
):
    """
    GET: Retrieve a specific network
    PUT/PATCH: Update a network
    DELETE: Deactivate a network
    """

    queryset = SurfaceMonitoringNetwork.objects.all()
    permission_classes = [
        (IsObjectDeletion & SDB_AdminAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = SurfaceMonitoringNetworkSerializer
    lookup_field = "id"
    lookup_url_kwarg = "network_id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Retrieve a specific network."""
        network = self.get_object()
        serializer = self.get_serializer(network)
        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        """Update a network."""
        network = self.get_object()
        serializer = self.get_serializer(network, data=request.data, partial=partial)

        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Full update of network."""
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Partial update of network."""
        return self._modify_obj(request=request, partial=True, **kwargs)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Deactivate a network instead of deleting it.

        Sets is_active=False to deactivate the network while preserving
        all data. Also deactivates all user permissions for the network.
        """
        user = self.get_user()
        network = self.get_object()

        # Deactivate all permissions
        for perm in network.permissions.all():
            perm.deactivate(deactivated_by=user)

        # Deactivate the network
        network.is_active = False
        network.save()

        return SuccessResponse(
            {"id": str(network.id), "message": "Network deleted successfully"}
        )


class SurfaceMonitoringNetworkPermissionApiView(
    GenericAPIView[SurfaceMonitoringNetwork], SDBAPIViewMixin
):
    """
    GET: List all permissions for a network
    POST: Grant permission to a user
    """

    queryset = SurfaceMonitoringNetwork.objects.all()
    permission_classes = [SDB_AdminAccess | (IsReadOnly & SDB_ReadAccess)]
    serializer_class = SurfaceMonitoringNetworkSerializer
    lookup_field = "id"
    lookup_url_kwarg = "network_id"

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
                            # network admin to create permission. So you obviously
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
        self, request: Request, network_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """List all active permissions for a network."""
        network = self.get_object()

        permissions = SurfaceMonitoringNetworkUserPermission.objects.filter(
            network=network,
            is_active=True,
        ).select_related("user")

        serializer = SurfaceMonitoringNetworkUserPermissionSerializer(
            permissions, many=True
        )
        return SuccessResponse(serializer.data)

    def post(
        self, request: Request, network_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        """Grant permission to a user (requires ADMIN access)."""
        network = self.get_object()

        perm_data = self._process_request_data(request=request, data=request.data)

        target_user: User = perm_data["user"]
        permission, created = (
            SurfaceMonitoringNetworkUserPermission.objects.get_or_create(
                user=target_user,
                network=network,
            )
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

        permission_serializer = SurfaceMonitoringNetworkUserPermissionSerializer(
            permission
        )
        network_serializer = self.get_serializer(network)

        # Refresh the `modified_date` field
        network.save()

        return SuccessResponse(
            {
                "network": network_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        network = self.get_object()
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
            permission = SurfaceMonitoringNetworkUserPermission.objects.get(
                user=target_user,
                network=network,
            )

        except ObjectDoesNotExist as e:
            raise Http404(
                f"A permission for this user: `{target_user}` does not exist."
            ) from e

        permission.level = perm_data["level"]
        permission.save()

        permission_serializer = SurfaceMonitoringNetworkUserPermissionSerializer(
            permission
        )
        network_serializer = self.get_serializer(network)

        # Refresh the `modified_date` field
        network.save()
        return SuccessResponse(
            {
                "network": network_serializer.data,
                "permission": permission_serializer.data,
            }
        )

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        network = self.get_object()
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
            permission = SurfaceMonitoringNetworkUserPermission.objects.get(
                network=network,
                user=target_user,
                is_active=True,
            )

        except ObjectDoesNotExist as e:
            raise Http404(
                f"A permission for this user: `{target_user}` does not exist."
            ) from e

        permission.deactivate(deactivated_by=user)

        network_serializer = self.get_serializer(network)

        # Refresh the `modified_date` field
        network.save()

        return SuccessResponse(
            {
                "network": network_serializer.data,
            },
            status=status.HTTP_200_OK,
        )
