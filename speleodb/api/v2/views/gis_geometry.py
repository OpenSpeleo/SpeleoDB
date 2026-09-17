"""Private authoring and sharing endpoints for GIS Geometry."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v2.direct_user_permissions import DirectUserPermissionData
from speleodb.api.v2.direct_user_permissions import parse_direct_user_permission_data
from speleodb.api.v2.gis_geometry_access import accessible_gis_geometries_queryset
from speleodb.api.v2.permissions import IsObjectDeletion
from speleodb.api.v2.permissions import IsObjectEdition
from speleodb.api.v2.permissions import IsReadOnly
from speleodb.api.v2.permissions import SDB_AdminAccess
from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.permissions import SDB_WriteAccess
from speleodb.api.v2.serializers.gis_geometry import GISGeometryListSerializer
from speleodb.api.v2.serializers.gis_geometry import GISGeometrySerializer
from speleodb.api.v2.serializers.gis_geometry import GISGeometryUpdateSerializer
from speleodb.api.v2.serializers.gis_geometry import GISGeometryUserPermissionSerializer
from speleodb.gis.geometry_services import GISGeometryConflictError
from speleodb.gis.geometry_services import update_gis_geometry
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISGeometryUserPermission
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.requests import require_mapping_request_data
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response


def _validation_error(exc: ValidationError) -> ErrorResponse:
    errors: Any = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    return ErrorResponse({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)


class GISGeometryCollectionAPIView(GenericAPIView[GISGeometry], SDBAPIViewMixin):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GISGeometrySerializer
    queryset = GISGeometry.objects.filter(is_active=True)

    @extend_schema(responses=GISGeometryListSerializer(many=True))
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        geometries = accessible_gis_geometries_queryset(self.get_user()).defer(
            "geojson"
        )
        return SuccessResponse(GISGeometryListSerializer(geometries, many=True).data)

    @extend_schema(responses={201: GISGeometrySerializer})
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            geometry = serializer.save()
        except ValidationError as exc:
            return _validation_error(exc)
        return SuccessResponse(
            GISGeometrySerializer(geometry).data, status=status.HTTP_201_CREATED
        )


class GISGeometrySpecificAPIView(GenericAPIView[GISGeometry], SDBAPIViewMixin):
    permission_classes = [
        (IsObjectDeletion & SDB_AdminAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = GISGeometrySerializer
    queryset = GISGeometry.objects.filter(is_active=True)
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[GISGeometry]:
        queryset = accessible_gis_geometries_queryset(self.get_user())
        return (
            queryset.select_for_update()
            if self.request.method == "DELETE"
            else queryset
        )

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return SuccessResponse(self.get_serializer(self.get_object()).data)

    @extend_schema(request=GISGeometryUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        geometry: GISGeometry = self.get_object()
        serializer = GISGeometryUpdateSerializer(
            geometry, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )
        updates: dict[str, Any] = dict(serializer.validated_data)
        expected_revision: int = updates.pop("expected_revision")
        try:
            geometry = update_gis_geometry(
                geometry_id=geometry.id,
                actor=self.get_user(),
                expected_revision=expected_revision,
                updates=updates,
            )
        except GISGeometryConflictError as exc:
            return ErrorResponse(
                {"error": exc.messages[0], "code": "GIS_GEOMETRY_CONFLICT"},
                status=status.HTTP_409_CONFLICT,
            )
        except ValidationError as exc:
            return _validation_error(exc)
        geometry = self.get_queryset().get(id=geometry.id)
        return SuccessResponse(self.get_serializer(geometry).data)

    @transaction.atomic
    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        geometry: GISGeometry = self.get_object()
        geometry.deactivate(self.get_user())
        return SuccessResponse(
            {"id": str(geometry.id), "message": "GIS Geometry deleted successfully"}
        )


class GISGeometryPermissionAPIView(GenericAPIView[GISGeometry], SDBAPIViewMixin):
    """List and manage direct-user access, serialized with geometry edits."""

    queryset = GISGeometry.objects.filter(is_active=True)
    permission_classes = [SDB_AdminAccess | (IsReadOnly & SDB_ReadAccess)]
    serializer_class = GISGeometrySerializer
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[GISGeometry]:
        queryset = accessible_gis_geometries_queryset(self.get_user())
        # get_object() checks current access after acquiring the geometry lock,
        # so queued sharing changes cannot bypass a committed revocation.
        return (
            queryset.select_for_update()
            if self.request.method in {"POST", "PUT", "DELETE"}
            else queryset
        )

    def _request_data(
        self,
        request: Request,
        *,
        skip_level: bool = False,
    ) -> DirectUserPermissionData:
        data = require_mapping_request_data(request.data)
        return parse_direct_user_permission_data(
            request_user=self.get_user(),
            data=data,
            skip_level=skip_level,
        )

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        geometry: GISGeometry = self.get_object()
        permission_qs = (
            GISGeometryUserPermission.objects.filter(
                gis_geometry=geometry, is_active=True
            )
            .select_related("user", "gis_geometry")
            .order_by("-level", "user__email")
        )
        return SuccessResponse(
            GISGeometryUserPermissionSerializer(permission_qs, many=True).data
        )

    @transaction.atomic
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        geometry: GISGeometry = self.get_object()
        permission_data = self._request_data(request)
        target_user = permission_data["user"]
        level = permission_data["level"]
        try:
            with transaction.atomic():
                permission, created = GISGeometryUserPermission.objects.get_or_create(
                    user=target_user,
                    gis_geometry=geometry,
                    defaults={"level": level},
                )
        except IntegrityError:
            permission = GISGeometryUserPermission.objects.get(
                user=target_user,
                gis_geometry=geometry,
            )
            created = False
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
        geometry.save(update_fields=["modified_date"])
        return SuccessResponse(
            {
                "gis_geometry": self.get_serializer(geometry).data,
                "permission": GISGeometryUserPermissionSerializer(permission).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        geometry: GISGeometry = self.get_object()
        permission_data = self._request_data(request)
        target_user = permission_data["user"]
        try:
            permission = GISGeometryUserPermission.objects.get(
                user=target_user,
                gis_geometry=geometry,
                is_active=True,
            )
        except GISGeometryUserPermission.DoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this user: `{target_user}` does not exist."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        permission.level = permission_data["level"]
        permission.save(update_fields=["level", "modified_date"])
        geometry.save(update_fields=["modified_date"])
        return SuccessResponse(GISGeometryUserPermissionSerializer(permission).data)

    @transaction.atomic
    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        geometry: GISGeometry = self.get_object()
        permission_data = self._request_data(request, skip_level=True)
        target_user = permission_data["user"]
        try:
            permission = GISGeometryUserPermission.objects.get(
                user=target_user,
                gis_geometry=geometry,
                is_active=True,
            )
        except GISGeometryUserPermission.DoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this user: `{target_user}` does not exist."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        permission.deactivate(deactivated_by=self.get_user())
        geometry.save(update_fields=["modified_date"])
        return SuccessResponse(
            {
                "message": (
                    f"Permission revoked for {target_user.email} on {geometry.name}."
                )
            }
        )
