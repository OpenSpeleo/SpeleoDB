# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from django.db import IntegrityError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser
from rest_framework.parsers import MultiPartParser

from speleodb.api.v2.direct_user_permissions import DirectUserPermissionData
from speleodb.api.v2.direct_user_permissions import parse_direct_user_permission_data
from speleodb.api.v2.gis_layer_access import accessible_gis_layers_queryset
from speleodb.api.v2.permissions import IsObjectDeletion
from speleodb.api.v2.permissions import IsObjectEdition
from speleodb.api.v2.permissions import IsReadOnly
from speleodb.api.v2.permissions import SDB_AdminAccess
from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.permissions import SDB_WriteAccess
from speleodb.api.v2.serializers import GISLayerCreateSerializer
from speleodb.api.v2.serializers import GISLayerSerializer
from speleodb.api.v2.serializers import GISLayerUserPermissionSerializer
from speleodb.gis.gis_layer_processing import GISLayerProcessingError
from speleodb.gis.gis_layer_processing import compile_gis_layer
from speleodb.gis.models import GISLayer
from speleodb.gis.models import GISLayerSourceFormat
from speleodb.gis.models import GISLayerUserPermission
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.db.models import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response

logger = logging.getLogger(__name__)


@method_decorator(transaction.non_atomic_requests, name="dispatch")
class GISLayerCollectionAPIView(GenericAPIView[GISLayer], SDBAPIViewMixin):
    """List readable layers or accept a multipart source upload."""

    queryset = GISLayer.objects.filter(is_active=True)
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GISLayerSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self) -> type[GISLayerSerializer]:
        if self.request.method == "POST":
            return GISLayerCreateSerializer
        return GISLayerSerializer

    @extend_schema(operation_id="v2_gis_layers_list")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        layers = accessible_gis_layers_queryset(user=self.get_user())
        return SuccessResponse(GISLayerSerializer(layers, many=True).data)

    @extend_schema(
        operation_id="v2_gis_layers_create",
        request=GISLayerCreateSerializer,
        responses={
            201: GISLayerSerializer,
            400: OpenApiTypes.OBJECT,
            422: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = cast(
            "GISLayerCreateSerializer",
            self.get_serializer(data=request.data),
        )
        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        source_file = serializer.validated_data["source_file"]
        compilation_result = None
        try:
            if (
                serializer.declared_source_format(source_file.name)
                != GISLayerSourceFormat.GEOJSON
            ):
                compilation_result = compile_gis_layer(
                    source_file,
                    filename=source_file.name,
                )
        except GISLayerProcessingError as exc:
            logger.info(
                "GIS Layer upload rejected during synchronous compilation.",
                extra={
                    "gis_layer_upload": {
                        "error_code": exc.code.value,
                        "source_bytes": source_file.size,
                    }
                },
            )
            return ErrorResponse(
                {
                    "error": exc.user_message,
                    "code": exc.code.value,
                    "details": exc.details,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        finally:
            source_file.seek(0)

        try:
            layer = serializer.save(compilation_result=compilation_result)
        except Exception:
            logger.exception(
                "GIS Layer publication failed after successful compilation."
            )
            return ErrorResponse(
                {
                    "error": "The GIS Layer could not be stored. Please try again.",
                    "code": "GIS_LAYER_PUBLICATION_FAILED",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return SuccessResponse(
            GISLayerSerializer(layer).data,
            status=status.HTTP_201_CREATED,
        )


class GISLayerSpecificAPIView(GenericAPIView[GISLayer], SDBAPIViewMixin):
    """Retrieve, edit, or soft-delete one private GIS Layer."""

    queryset = GISLayer.objects.filter(is_active=True)
    permission_classes = [
        (IsObjectDeletion & SDB_AdminAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = GISLayerSerializer
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[GISLayer]:
        return accessible_gis_layers_queryset(user=self.get_user())

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return SuccessResponse(self.get_serializer(self.get_object()).data)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        layer = self.get_object()
        serializer = self.get_serializer(layer, data=request.data, partial=True)
        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return SuccessResponse(serializer.data)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        layer = self.get_object()
        layer.deactivate(deactivated_by=self.get_user())
        return SuccessResponse(
            {
                "id": str(layer.id),
                "message": "GIS Layer deleted successfully",
            }
        )


class GISLayerSourceAPIView(GenericAPIView[GISLayer], SDBAPIViewMixin):
    """Authorize and redirect to the original source file."""

    queryset = GISLayer.objects.filter(is_active=True)
    permission_classes = [SDB_ReadAccess]
    serializer_class = GISLayerSerializer
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[GISLayer]:
        return accessible_gis_layers_queryset(user=self.get_user())

    @extend_schema(
        responses={
            302: OpenApiResponse(
                description="Redirect to a signed private source URL."
            ),
            404: OpenApiTypes.OBJECT,
        }
    )
    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirect | ErrorResponse:
        layer = self.get_object()
        if not layer.source_f:
            return ErrorResponse(
                {"error": "The GIS Layer source does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return HttpResponseRedirect(layer.get_signed_source_url())


class GISLayerPermissionAPIView(GenericAPIView[GISLayer], SDBAPIViewMixin):
    """List and manage durable direct-user access to one active GIS Layer."""

    queryset = GISLayer.objects.filter(is_active=True)
    permission_classes = [SDB_AdminAccess | (IsReadOnly & SDB_ReadAccess)]
    serializer_class = GISLayerSerializer
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[GISLayer]:
        return accessible_gis_layers_queryset(user=self.get_user())

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
        layer = self.get_object()
        permission_qs = (
            GISLayerUserPermission.objects.filter(gis_layer=layer, is_active=True)
            .select_related("user", "gis_layer")
            .order_by("-level", "user__email")
        )
        return SuccessResponse(
            GISLayerUserPermissionSerializer(permission_qs, many=True).data
        )

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        layer = self.get_object()
        permission_data = self._request_data(request)
        target_user = permission_data["user"]
        level = permission_data["level"]
        try:
            with transaction.atomic():
                permission, created = GISLayerUserPermission.objects.get_or_create(
                    user=target_user,
                    gis_layer=layer,
                    defaults={"level": level},
                )
        except IntegrityError:
            permission = GISLayerUserPermission.objects.get(
                user=target_user,
                gis_layer=layer,
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
        layer.save(update_fields=["modified_date"])
        return SuccessResponse(
            {
                "gis_layer": self.get_serializer(layer).data,
                "permission": GISLayerUserPermissionSerializer(permission).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        layer = self.get_object()
        permission_data = self._request_data(request)
        target_user = permission_data["user"]
        try:
            permission = GISLayerUserPermission.objects.get(
                user=target_user,
                gis_layer=layer,
                is_active=True,
            )
        except GISLayerUserPermission.DoesNotExist:
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
        layer.save(update_fields=["modified_date"])
        return SuccessResponse(GISLayerUserPermissionSerializer(permission).data)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        layer = self.get_object()
        permission_data = self._request_data(request, skip_level=True)
        target_user = permission_data["user"]
        try:
            permission = GISLayerUserPermission.objects.get(
                user=target_user,
                gis_layer=layer,
                is_active=True,
            )
        except GISLayerUserPermission.DoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this user: `{target_user}` does not exist."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        permission.deactivate(deactivated_by=self.get_user())
        layer.save(update_fields=["modified_date"])
        return SuccessResponse(
            {"message": f"Permission revoked for {target_user.email} on {layer.name}."}
        )
