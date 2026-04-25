# -*- coding: utf-8 -*-

from __future__ import annotations

import io
import logging
import re
from typing import TYPE_CHECKING
from typing import Any

import gpxpy.gpx
import xlsxwriter
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from django.http import Http404
from django.http import StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v2.landmark_access import accessible_landmark_collections_queryset
from speleodb.api.v2.landmark_access import collection_landmarks_queryset
from speleodb.api.v2.permissions import IsObjectDeletion
from speleodb.api.v2.permissions import IsObjectEdition
from speleodb.api.v2.permissions import IsReadOnly
from speleodb.api.v2.permissions import SDB_AdminAccess
from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.permissions import SDB_WriteAccess
from speleodb.api.v2.serializers.landmark_collection import LandmarkCollectionSerializer
from speleodb.api.v2.serializers.landmark_collection import (
    LandmarkCollectionUserPermissionSerializer,
)
from speleodb.api.v2.serializers.landmark_collection import (
    LandmarkCollectionWithPermSerializer,
)
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission
from speleodb.users.models import User
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.exceptions import BadRequestError
from speleodb.utils.exceptions import MissingFieldError
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


_LANDMARK_EXPORT_XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
_LANDMARK_EXPORT_GPX_CONTENT_TYPE = "application/gpx+xml"
_LANDMARK_EXPORT_GPX_CREATOR = "SpeleoDB"
_LANDMARK_EXPORT_GPX_VERSION = "1.1"
_PERSONAL_COLLECTION_EDITABLE_FIELDS = frozenset({"color"})


def _sanitize_export_filename(value: str) -> str:
    filename = re.sub(r'[\\/*?:"<>|]', "", value).strip()
    return filename or "landmarks"


class LandmarkCollectionApiView(GenericAPIView[LandmarkCollection], SDBAPIViewMixin):
    """GET/POST API for Landmark Collections."""

    queryset = LandmarkCollection.objects.filter(is_active=True)
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LandmarkCollectionSerializer

    @extend_schema(operation_id="v2_landmark_collections_list")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        collections = accessible_landmark_collections_queryset(user=user).annotate(
            landmark_count=Count("landmarks", distinct=True),
        )

        return SuccessResponse(
            LandmarkCollectionWithPermSerializer(collections, many=True).data
        )

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        data = request.data.copy()
        data["created_by"] = user.email

        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)


class LandmarkCollectionSpecificApiView(
    GenericAPIView[LandmarkCollection], SDBAPIViewMixin
):
    """GET/PUT/PATCH/DELETE API for one Landmark Collection."""

    queryset = LandmarkCollection.objects.filter(is_active=True).annotate(
        landmark_count=Count("landmarks", distinct=True),
    )
    permission_classes = [
        (IsObjectDeletion & SDB_AdminAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = LandmarkCollectionSerializer
    lookup_field = "id"
    lookup_url_kwarg = "collection_id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        collection = self.get_object()
        serializer = self.get_serializer(collection)
        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        collection = self.get_object()
        if collection.is_personal:
            requested_fields = set(request.data.keys())
            disallowed_fields = requested_fields - _PERSONAL_COLLECTION_EDITABLE_FIELDS
            if disallowed_fields:
                return ErrorResponse(
                    {
                        "error": (
                            "Personal landmark collections only allow color updates."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            partial = True

        serializer = self.get_serializer(
            collection,
            data=request.data,
            partial=partial,
        )

        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._modify_obj(request=request, partial=True, **kwargs)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        collection = self.get_object()
        if collection.is_personal:
            return ErrorResponse(
                {"error": "Personal landmark collections cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for permission in collection.permissions.filter(is_active=True):
            permission.deactivate(deactivated_by=user)

        collection.is_active = False
        collection.save(update_fields=["is_active", "modified_date"])

        return SuccessResponse(
            {
                "id": str(collection.id),
                "message": "Landmark collection deleted successfully",
            }
        )


class LandmarkCollectionPermissionApiView(
    GenericAPIView[LandmarkCollection], SDBAPIViewMixin
):
    """GET/POST/PUT/DELETE API for Landmark Collection user permissions."""

    queryset = LandmarkCollection.objects.filter(is_active=True).annotate(
        landmark_count=Count("landmarks", distinct=True),
    )
    permission_classes = [SDB_AdminAccess | (IsReadOnly & SDB_ReadAccess)]
    serializer_class = LandmarkCollectionSerializer
    lookup_field = "id"
    lookup_url_kwarg = "collection_id"

    def _process_request_data(
        self, request: Request, data: dict[str, Any], skip_level: bool = False
    ) -> dict[str, Any]:
        request_user = self.get_user()
        permission_data: dict[str, Any] = {}

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
                            permission_data[key] = PermissionLevel.from_str(
                                value.upper()
                            )
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

                        permission_data["user"] = user

                    case _:
                        raise ValueNotFoundError(f"Unknown key: {key}")

            except KeyError as e:
                raise MissingFieldError(f"Attribute: `{key}` is missing. {data}") from e

        return permission_data

    def get(
        self, request: Request, collection_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        collection = self.get_object()
        if collection.is_personal:
            return ErrorResponse(
                {
                    "error": (
                        "Personal landmark collection permissions cannot be managed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        permissions_qs = (
            LandmarkCollectionUserPermission.objects.filter(
                collection=collection,
                is_active=True,
            )
            .select_related("user", "collection")
            .order_by("-level", "user__email")
        )

        serializer = LandmarkCollectionUserPermissionSerializer(
            permissions_qs,
            many=True,
        )
        return SuccessResponse(serializer.data)

    def post(
        self, request: Request, collection_id: str, *args: Any, **kwargs: Any
    ) -> Response:
        collection = self.get_object()
        if collection.is_personal:
            return ErrorResponse(
                {
                    "error": (
                        "Personal landmark collection permissions cannot be managed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        permission_data = self._process_request_data(
            request=request,
            data=request.data,
        )

        target_user: User = permission_data["user"]
        permission, created = LandmarkCollectionUserPermission.objects.get_or_create(
            user=target_user,
            collection=collection,
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

            permission.reactivate(level=permission_data["level"])
        else:
            permission.level = permission_data["level"]
            permission.save()

        permission_serializer = LandmarkCollectionUserPermissionSerializer(permission)
        collection_serializer = self.get_serializer(collection)
        collection.save(update_fields=["modified_date"])

        return SuccessResponse(
            {
                "collection": collection_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        collection = self.get_object()
        if collection.is_personal:
            return ErrorResponse(
                {
                    "error": (
                        "Personal landmark collection permissions cannot be managed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        permission_data = self._process_request_data(
            request=request,
            data=request.data,
        )

        target_user: User = permission_data["user"]
        try:
            permission = LandmarkCollectionUserPermission.objects.get(
                user=target_user,
                collection=collection,
                is_active=True,
            )
        except ObjectDoesNotExist as e:
            raise Http404(
                f"A permission for this user: `{target_user}` does not exist."
            ) from e

        permission.level = permission_data["level"]
        permission.save(update_fields=["level", "modified_date"])
        collection.save(update_fields=["modified_date"])

        serializer = LandmarkCollectionUserPermissionSerializer(permission)
        return SuccessResponse(serializer.data)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        collection = self.get_object()
        if collection.is_personal:
            return ErrorResponse(
                {
                    "error": (
                        "Personal landmark collection permissions cannot be managed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        permission_data = self._process_request_data(
            request=request,
            data=request.data,
            skip_level=True,
        )

        target_user: User = permission_data["user"]
        try:
            permission = LandmarkCollectionUserPermission.objects.get(
                user=target_user,
                collection=collection,
                is_active=True,
            )
        except ObjectDoesNotExist as e:
            raise Http404(
                f"A permission for this user: `{target_user}` does not exist."
            ) from e

        permission.deactivate(deactivated_by=self.get_user())
        collection.save(update_fields=["modified_date"])

        return SuccessResponse(
            {
                "message": (
                    f"Permission revoked for {target_user.email} on {collection.name}."
                )
            }
        )


class LandmarkCollectionLandmarksExportExcelApiView(
    GenericAPIView[LandmarkCollection],
    SDBAPIViewMixin,
):
    """Export Landmark Collection Landmarks to Excel."""

    queryset = LandmarkCollection.objects.filter(is_active=True)
    permission_classes = [IsReadOnly & SDB_ReadAccess]
    serializer_class = LandmarkCollectionSerializer
    lookup_field = "id"
    lookup_url_kwarg = "collection_id"

    @extend_schema(
        operation_id="v2_landmark_collection_landmarks_export_excel",
        responses={(200, _LANDMARK_EXPORT_XLSX_CONTENT_TYPE): OpenApiTypes.BINARY},
    )
    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> StreamingHttpResponse:
        collection = self.get_object()
        landmarks = collection_landmarks_queryset(collection=collection)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Landmarks")

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

        headers = ["Name", "Longitude", "Latitude", "Created By"]
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, header_format)
            worksheet.set_column(col_num, col_num, max(len(header) + 2, 16))

        for row_num, landmark in enumerate(landmarks, start=1):
            worksheet.write(row_num, 0, landmark.name, cell_format)
            worksheet.write(row_num, 1, float(landmark.longitude), cell_format)
            worksheet.write(row_num, 2, float(landmark.latitude), cell_format)
            worksheet.write(row_num, 3, landmark.created_by, cell_format)

        workbook.close()
        output.seek(0)

        filename = (
            "landmark_collection_"
            f"{_sanitize_export_filename(collection.name)}_"
            f"{timezone.localdate().isoformat()}.xlsx"
        )
        response = StreamingHttpResponse(
            output,
            content_type=_LANDMARK_EXPORT_XLSX_CONTENT_TYPE,
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class LandmarkCollectionLandmarksExportGPXApiView(
    GenericAPIView[LandmarkCollection],
    SDBAPIViewMixin,
):
    """Export Landmark Collection Landmarks to GPX waypoints."""

    queryset = LandmarkCollection.objects.filter(is_active=True)
    permission_classes = [IsReadOnly & SDB_ReadAccess]
    serializer_class = LandmarkCollectionSerializer
    lookup_field = "id"
    lookup_url_kwarg = "collection_id"

    @extend_schema(
        operation_id="v2_landmark_collection_landmarks_export_gpx",
        responses={(200, _LANDMARK_EXPORT_GPX_CONTENT_TYPE): OpenApiTypes.BINARY},
    )
    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> StreamingHttpResponse:
        collection = self.get_object()
        landmarks = collection_landmarks_queryset(collection=collection)

        gpx = gpxpy.gpx.GPX()
        gpx.creator = _LANDMARK_EXPORT_GPX_CREATOR
        gpx.version = _LANDMARK_EXPORT_GPX_VERSION
        gpx.name = collection.name
        gpx.description = collection.description

        for landmark in landmarks:
            description_parts: list[str] = []
            if landmark.description:
                description_parts.append(landmark.description)
            description_parts.append(f"Created by: {landmark.created_by}")

            gpx.waypoints.append(
                gpxpy.gpx.GPXWaypoint(
                    latitude=float(landmark.latitude),
                    longitude=float(landmark.longitude),
                    name=landmark.name,
                    description="\n".join(description_parts),
                )
            )

        filename = (
            "landmark_collection_"
            f"{_sanitize_export_filename(collection.name)}_"
            f"{timezone.localdate().isoformat()}.gpx"
        )
        response = StreamingHttpResponse(
            [gpx.to_xml(version=_LANDMARK_EXPORT_GPX_VERSION).encode("utf-8")],
            content_type=_LANDMARK_EXPORT_GPX_CONTENT_TYPE,
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
