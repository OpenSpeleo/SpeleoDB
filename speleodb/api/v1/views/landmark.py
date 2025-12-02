# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import LandmarkOwnershipPermission
from speleodb.api.v1.serializers.landmark import LandmarkGeoJSONSerializer
from speleodb.api.v1.serializers.landmark import LandmarkSerializer
from speleodb.gis.models import Landmark
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response


class LandmarkSpecificAPIView(GenericAPIView[Landmark], SDBAPIViewMixin):
    """API View for managing personal Landmarks.

    Landmarks are personal/private - users can only see and modify their own Landmarks.
    - Shows only Landmarks created by the authenticated user
    - Requires authentication and ownership
    """

    queryset = Landmark.objects.all().select_related("user")
    permission_classes = [LandmarkOwnershipPermission]
    serializer_class = LandmarkSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get detailed Landmark information (only if owned by user)."""
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
        """Update a Landmark (only if owned by user)."""
        landmark = self.get_object()

        serializer = self.get_serializer(landmark, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse({"landmark": serializer.data})

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete a Landmark (only if owned by user)."""
        landmark = self.get_object()
        landmark_id = landmark.id
        landmark.delete()
        return SuccessResponse(
            {"message": f"Landmark {landmark_id} deleted successfully"}
        )


class LandmarkAPIView(GenericAPIView[Landmark], SDBAPIViewMixin):
    """API View for managing personal Landmarks.

    Landmarks are personal/private - users can only see and modify their own Landmarks.
    - Shows only Landmarks created by the authenticated user
    - Requires authentication and ownership
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LandmarkSerializer
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[Landmark]:
        """Get only Landmarks created by the authenticated user."""
        user = self.get_user()
        return Landmark.objects.filter(user=user).select_related("user")

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return SuccessResponse({"landmarks": serializer.data})

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new Landmark for the authenticated user."""
        user = self.get_user()

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user)
            return SuccessResponse(
                {"landmark": serializer.data},
                status=status.HTTP_201_CREATED,
            )

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class LandmarkGeoJSONView(GenericAPIView[Landmark], SDBAPIViewMixin):
    """
    View to get user's Landmarks as GeoJSON-compatible data.
    Used by the map viewer to display Landmark markers.
    Only shows Landmarks created by the authenticated user.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LandmarkGeoJSONSerializer

    def get_queryset(self) -> QuerySet[Landmark]:
        """Get only Landmarks created by the authenticated user."""
        user = self.get_user()
        return Landmark.objects.filter(user=user).select_related("user")

    def get(self, request: Request) -> Response:
        """Get user's Landmarks in a map-friendly format."""
        landmarks = self.get_queryset()

        # Use the map serializer to convert to GeoJSON format
        serializer = self.get_serializer(landmarks, many=True)
        features = serializer.data

        return SuccessResponse({"type": "FeatureCollection", "features": features})
