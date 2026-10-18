# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.db import IntegrityError
from django.db import transaction
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework import serializers
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.schema_errors import API_ERROR
from speleodb.api.schema_helpers import response_object
from speleodb.api.v2.permissions import SDB_WriteAccess
from speleodb.api.v2.serializers.station_tag import StationTagSerializer
from speleodb.gis.models import Station
from speleodb.gis.models import StationTag
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.requests import require_mapping_request_data
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from django.db.models.query import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response


class StationTagsApiView(GenericAPIView[StationTag], SDBAPIViewMixin):
    """
    View to list and create station tags for the authenticated user.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StationTagSerializer

    def get_queryset(self) -> QuerySet[StationTag]:
        """Get only tags that belong to the authenticated user."""
        user = self.get_user()
        return StationTag.objects.filter(user=user)

    @extend_schema(operation_id="v2_station_tags_list")
    @extend_schema(responses={200: StationTagSerializer(many=True), 403: API_ERROR})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List all tags for the authenticated user."""
        tags = self.get_queryset()
        serializer = self.get_serializer(tags, many=True)
        return SuccessResponse(serializer.data)

    @extend_schema(
        responses={201: StationTagSerializer(), 400: API_ERROR, 403: API_ERROR}
    )
    @extend_schema(operation_id="v2_station_tags_create")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new station tag for the authenticated user."""
        user = self.get_user()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    serializer.save(user=user)

                return SuccessResponse(
                    serializer.data,
                    status=status.HTTP_201_CREATED,
                )

            except IntegrityError:
                return ErrorResponse(
                    {
                        "error": (
                            f"A tag with the name '{serializer.validated_data['name']}'"
                            " already exists for this user."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class StationTagSpecificApiView(GenericAPIView[StationTag], SDBAPIViewMixin):
    """
    View to get, update, or delete a specific station tag.
    Users can only access their own tags.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StationTagSerializer
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[StationTag]:
        """Get only tags that belong to the authenticated user."""
        user = self.get_user()
        return StationTag.objects.filter(user=user)

    @extend_schema(
        responses={200: StationTagSerializer(), 403: API_ERROR, 404: API_ERROR}
    )
    @extend_schema(operation_id="v2_station_tags_retrieve")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get a specific station tag."""
        tag = self.get_object()
        serializer = self.get_serializer(tag)
        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        """Update a station tag."""
        tag = self.get_object()
        serializer = self.get_serializer(tag, data=request.data, partial=partial)

        if serializer.is_valid():
            try:
                serializer.save()
                return SuccessResponse(serializer.data)
            except IntegrityError:
                return ErrorResponse(
                    {
                        "error": (
                            "A tag with the name "
                            f"{serializer.validated_data.get('name', tag.name)}' "
                            "already exists for this user."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @extend_schema(operation_id="v2_station_tags_update")
    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Full update of a station tag."""
        return self._modify_obj(request=request, partial=False, **kwargs)

    @extend_schema(operation_id="v2_station_tags_partial_update")
    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Partial update of a station tag."""
        return self._modify_obj(request=request, partial=True, **kwargs)

    @extend_schema(
        responses={
            200: response_object(
                "StationTagSpecificApiViewDeleteResponse", id=serializers.UUIDField()
            ),
            403: API_ERROR,
        }
    )
    @extend_schema(operation_id="v2_station_tags_destroy")
    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete a station tag."""
        tag = self.get_object()
        tag_id = tag.id
        tag.delete()
        return SuccessResponse({"id": str(tag_id)})


class StationTagColorsApiView(GenericAPIView[StationTag], SDBAPIViewMixin):
    """
    View to get the list of predefined colors for station tags.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={
            200: {
                "type": "object",
                "properties": {
                    "colors": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["colors"],
                "additionalProperties": False,
            },
            403: API_ERROR,
        },
    )
    @extend_schema(operation_id="v2_station_tags_colors_retrieve")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get list of predefined colors."""
        return SuccessResponse({"colors": StationTag.get_predefined_colors()})


class StationTagsManageApiView(GenericAPIView[Station], SDBAPIViewMixin):
    """
    View to manage tag on a specific station.
    Allows setting/clearing a single tag on a station.
    """

    queryset = Station.objects.all()
    permission_classes = [SDB_WriteAccess]
    serializer_class = StationTagSerializer  # type: ignore[assignment]
    lookup_field = "id"

    @extend_schema(
        responses={
            200: {
                "anyOf": [
                    {"$ref": "#/components/schemas/StationTag"},
                    {"type": "string", "nullable": True, "enum": [None]},
                ]
            },
            403: API_ERROR,
            404: API_ERROR,
        }
    )
    @extend_schema(responses={200: StationTagSerializer(), 403: API_ERROR})
    @extend_schema(operation_id="v2_stations_tags_retrieve")
    def get(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response | JsonResponse:
        """Get the tag assigned to a station."""
        station = self.get_object()
        if station.tag:
            serializer = StationTagSerializer(station.tag)
            return SuccessResponse(serializer.data)
        # DRF renders Response(None) as empty bytes, which is not JSON null.
        return JsonResponse(None, safe=False)

    @extend_schema(
        request=response_object(
            "StationTagAssignmentRequest", tag_id=serializers.UUIDField()
        )
    )
    @extend_schema(
        responses={200: StationTagSerializer(), 400: API_ERROR, 403: API_ERROR}
    )
    @extend_schema(operation_id="v2_stations_tags_create")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Set a tag on a station."""
        station = self.get_object()
        user = self.get_user()

        request_data = require_mapping_request_data(request.data)
        tag_id = request_data.get("tag_id")
        if not tag_id:
            return ErrorResponse(
                {"error": "tag_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify tag exists and belongs to the user
        try:
            tag = StationTag.objects.get(id=tag_id, user=user)
        except StationTag.DoesNotExist:
            return ErrorResponse(
                {"error": "Tag does not exist or does not belong to you."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set tag on station
        station.tag = tag
        station.save()

        # Return the tag
        serializer = StationTagSerializer(station.tag)
        return SuccessResponse(serializer.data)

    @extend_schema(responses={200: None, 403: API_ERROR, 404: API_ERROR})
    @extend_schema(
        responses={
            200: {"type": "string", "nullable": True, "enum": [None]},
            403: API_ERROR,
            404: API_ERROR,
        }
    )
    @extend_schema(operation_id="v2_stations_tags_destroy")
    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Remove the tag from a station."""
        station = self.get_object()

        # Clear tag from station
        station.tag = None
        station.save()

        return SuccessResponse(None)
