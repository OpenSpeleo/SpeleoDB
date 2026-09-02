# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v2.direct_user_permissions import DirectUserPermissionData
from speleodb.api.v2.direct_user_permissions import parse_direct_user_permission_data
from speleodb.api.v2.gps_track_access import accessible_gps_tracks_queryset
from speleodb.api.v2.permissions import IsObjectDeletion
from speleodb.api.v2.permissions import IsObjectEdition
from speleodb.api.v2.permissions import IsReadOnly
from speleodb.api.v2.permissions import SDB_AdminAccess
from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.permissions import SDB_WriteAccess
from speleodb.api.v2.serializers import GPSTrackSerializer
from speleodb.api.v2.serializers import GPSTrackUserPermissionSerializer
from speleodb.api.v2.serializers import GPSTrackWithFileSerializer
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import GPSTrackUserPermission
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.db.models import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response


class UserGPSTracks(GenericAPIView[GPSTrack], SDBAPIViewMixin):
    """List active GPS Tracks readable by the authenticated user."""

    queryset = GPSTrack.objects.filter(is_active=True)
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GPSTrackWithFileSerializer

    @extend_schema(operation_id="v2_gps_tracks_list")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        tracks = accessible_gps_tracks_queryset(user=self.get_user())
        return SuccessResponse(self.get_serializer(tracks, many=True).data)


class GPSTrackSpecificAPIView(GenericAPIView[GPSTrack], SDBAPIViewMixin):
    """Retrieve, edit, or soft-delete one shared GPS Track."""

    queryset = GPSTrack.objects.filter(is_active=True)
    permission_classes = [
        (IsObjectDeletion & SDB_AdminAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = GPSTrackSerializer
    lookup_field = "id"

    def get_serializer_class(self) -> type[GPSTrackSerializer]:
        if self.request.method == "GET":
            return GPSTrackWithFileSerializer
        return GPSTrackSerializer

    def get_queryset(self) -> QuerySet[GPSTrack]:
        return accessible_gps_tracks_queryset(user=self.get_user())

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gps_track = self.get_object()
        return SuccessResponse(self.get_serializer(gps_track).data)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._update(request=request, partial=True, **kwargs)

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._update(request=request, partial=False, **kwargs)

    def _update(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        gps_track = self.get_object()
        serializer = self.get_serializer(
            gps_track,
            data=request.data,
            partial=partial,
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gps_track = self.get_object()
        gps_track.deactivate(deactivated_by=self.get_user())
        return SuccessResponse(
            {
                "id": str(gps_track.id),
                "message": "GPS Track deleted successfully",
            }
        )


class GPSTrackPermissionAPIView(GenericAPIView[GPSTrack], SDBAPIViewMixin):
    """List and manage direct-user access to one active GPS Track."""

    queryset = GPSTrack.objects.filter(is_active=True)
    permission_classes = [SDB_AdminAccess | (IsReadOnly & SDB_ReadAccess)]
    serializer_class = GPSTrackSerializer
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[GPSTrack]:
        return accessible_gps_tracks_queryset(user=self.get_user())

    def _request_data(
        self,
        request: Request,
        *,
        skip_level: bool = False,
    ) -> DirectUserPermissionData:
        data = cast("Mapping[str, Any]", request.data)
        return parse_direct_user_permission_data(
            request_user=self.get_user(),
            data=data,
            skip_level=skip_level,
        )

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gps_track = self.get_object()
        permission_qs = (
            GPSTrackUserPermission.objects.filter(
                gps_track=gps_track,
                is_active=True,
            )
            .select_related("user", "gps_track")
            .order_by("-level", "user__email")
        )
        serializer = GPSTrackUserPermissionSerializer(permission_qs, many=True)
        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gps_track = self.get_object()
        permission_data = self._request_data(request)
        target_user = permission_data["user"]
        level = permission_data["level"]
        permission, created = GPSTrackUserPermission.objects.get_or_create(
            user=target_user,
            gps_track=gps_track,
            defaults={"level": level},
        )

        if not created:
            if permission.is_active:
                return ErrorResponse(
                    {
                        "error": (
                            f"A permission for this user: `{target_user}` "
                            "already exists."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            permission.reactivate(level=level)

        gps_track.save(update_fields=["modified_date"])
        return SuccessResponse(
            {
                "gps_track": self.get_serializer(gps_track).data,
                "permission": GPSTrackUserPermissionSerializer(permission).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gps_track = self.get_object()
        permission_data = self._request_data(request)
        target_user = permission_data["user"]
        level = permission_data["level"]
        try:
            permission = GPSTrackUserPermission.objects.get(
                user=target_user,
                gps_track=gps_track,
                is_active=True,
            )
        except GPSTrackUserPermission.DoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this user: `{target_user}` does not exist."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        permission.level = level
        permission.save(update_fields=["level", "modified_date"])
        gps_track.save(update_fields=["modified_date"])
        return SuccessResponse(GPSTrackUserPermissionSerializer(permission).data)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gps_track = self.get_object()
        permission_data = self._request_data(request, skip_level=True)
        target_user = permission_data["user"]
        try:
            permission = GPSTrackUserPermission.objects.get(
                user=target_user,
                gps_track=gps_track,
                is_active=True,
            )
        except GPSTrackUserPermission.DoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this user: `{target_user}` does not exist."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        permission.deactivate(deactivated_by=self.get_user())
        gps_track.save(update_fields=["modified_date"])
        return SuccessResponse(
            {
                "message": (
                    f"Permission revoked for {target_user.email} on {gps_track.name}."
                )
            }
        )
