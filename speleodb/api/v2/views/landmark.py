# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.db import transaction
from django.db.utils import IntegrityError
from drf_spectacular.utils import extend_schema
from geojson import FeatureCollection  # type: ignore[attr-defined]
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v2.landmark_access import accessible_landmarks_queryset
from speleodb.api.v2.permissions import IsObjectDeletion
from speleodb.api.v2.permissions import IsObjectEdition
from speleodb.api.v2.permissions import IsReadOnly
from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.permissions import SDB_WriteAccess
from speleodb.api.v2.serializers.landmark import LandmarkGeoJSONSerializer
from speleodb.api.v2.serializers.landmark import LandmarkSerializer
from speleodb.gis.models import Landmark
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import NoWrapResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response


class LandmarkSpecificAPIView(GenericAPIView[Landmark], SDBAPIViewMixin):
    """API view for managing Landmarks through collection permissions."""

    queryset = Landmark.objects.filter(collection__is_active=True).select_related(
        "collection"
    )
    permission_classes = [
        (IsObjectDeletion & SDB_WriteAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = LandmarkSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get detailed Landmark information when the user has collection access."""
        landmark = self.get_object()
        serializer = self.get_serializer(landmark)
        return SuccessResponse({"landmark": serializer.data})

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._update(request=request, partial=True, **kwargs)

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._update(request=request, partial=False, **kwargs)

    def _update(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        """Update a Landmark when the user has collection WRITE access."""
        landmark = self.get_object()

        serializer = self.get_serializer(landmark, data=request.data, partial=partial)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    serializer.save()
                return SuccessResponse({"landmark": serializer.data})
            except IntegrityError:
                lat = serializer.validated_data.get("latitude", landmark.latitude)
                long = serializer.validated_data.get("longitude", landmark.longitude)
                return ErrorResponse(
                    {
                        "error": (
                            "A landmark for GPS coordinate "
                            f"({lat}, {long}) already exists or is invalid."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete a Landmark when the user has collection WRITE access."""
        landmark = self.get_object()
        landmark_id = landmark.id
        landmark.delete()
        return SuccessResponse(
            {"message": f"Landmark {landmark_id} deleted successfully"}
        )


class LandmarkAPIView(GenericAPIView[Landmark], SDBAPIViewMixin):
    """API view for listing and creating collection-backed Landmarks."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LandmarkSerializer
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[Landmark]:
        """Get Landmarks visible to the authenticated user."""
        user = self.get_user()
        return accessible_landmarks_queryset(user=user)

    @extend_schema(operation_id="v2_landmarks_list")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return SuccessResponse({"landmarks": serializer.data})

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new Landmark in a writable collection."""
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    serializer.save()
                return SuccessResponse(
                    {"landmark": serializer.data},
                    status=status.HTTP_201_CREATED,
                )
            except IntegrityError:
                lat = serializer.validated_data.get("latitude")
                long = serializer.validated_data.get("longitude")
                return ErrorResponse(
                    {
                        "error": (
                            "A landmark for GPS coordinate "
                            f"({lat}, {long}) already exists or is invalid."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class LandmarkGeoJSONView(GenericAPIView[Landmark], SDBAPIViewMixin):
    """
    View to get user's Landmarks as GeoJSON-compatible data.
    Used by the map viewer to display Landmark markers.
    Only shows Landmarks visible through active collection permissions.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LandmarkGeoJSONSerializer

    def get_queryset(self) -> QuerySet[Landmark]:
        """Get Landmarks visible to the authenticated user."""
        user = self.get_user()
        return accessible_landmarks_queryset(user=user)

    def get(self, request: Request) -> Response:
        """Get user's Landmarks in a map-friendly format."""
        landmarks = self.get_queryset()

        # Use the map serializer to convert to GeoJSON format
        serializer = self.get_serializer(landmarks, many=True)

        return NoWrapResponse(FeatureCollection(serializer.data))  # type: ignore[no-untyped-call]
