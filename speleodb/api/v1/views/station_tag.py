# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.db import IntegrityError
from django.db import transaction
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import SDB_WriteAccess
from speleodb.api.v1.serializers.station_tag import StationTagSerializer
from speleodb.gis.models import Station
from speleodb.gis.models import StationTag
from speleodb.utils.api_mixin import SDBAPIViewMixin
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

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List all tags for the authenticated user."""
        tags = self.get_queryset()
        serializer = self.get_serializer(tags, many=True)
        return SuccessResponse(serializer.data)

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

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Full update of a station tag."""
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Partial update of a station tag."""
        return self._modify_obj(request=request, partial=True, **kwargs)

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
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get the tag assigned to a station."""
        station = self.get_object()
        if station.tag:
            serializer = StationTagSerializer(station.tag)
            return SuccessResponse(serializer.data)
        return SuccessResponse(None)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Set a tag on a station."""
        station = self.get_object()
        user = self.get_user()

        tag_id = request.data.get("tag_id")
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
        station.save()  # type: ignore[no-untyped-call]

        # Return the tag
        serializer = StationTagSerializer(station.tag)
        return SuccessResponse(serializer.data)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Remove the tag from a station."""
        station = self.get_object()

        # Clear tag from station
        station.tag = None
        station.save()  # type: ignore[no-untyped-call]

        return SuccessResponse(None)
