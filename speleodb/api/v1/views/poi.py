# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import LandmarkOwnershipPermission
from speleodb.api.v1.serializers.poi import LandmarkGeoJSONSerializer
from speleodb.api.v1.serializers.poi import LandmarkSerializer
from speleodb.gis.models import Landmark
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response


class LandmarkSpecificAPIView(GenericAPIView[Landmark], SDBAPIViewMixin):
    """API View for managing personal Points of Interest.

    POIs are personal/private - users can only see and modify their own POIs.
    - Shows only POIs created by the authenticated user
    - Requires authentication and ownership
    """

    queryset = Landmark.objects.all().select_related("user")
    permission_classes = [LandmarkOwnershipPermission]
    serializer_class = LandmarkSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get detailed POI information (only if owned by user)."""
        poi = self.get_object()
        serializer = self.get_serializer(poi)
        return SuccessResponse({"poi": serializer.data})

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._update(request=request, partial=True, **kwargs)

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._update(request=request, partial=False, **kwargs)

    def _update(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        """Update a POI (only if owned by user)."""
        poi = self.get_object()

        serializer = self.get_serializer(poi, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse({"poi": serializer.data})

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete a POI (only if owned by user)."""
        poi = self.get_object()
        poi_id = poi.id
        poi.delete()
        return SuccessResponse(
            {"message": f"Point of Interest {poi_id} deleted successfully"}
        )


class LandmarkAPIView(GenericAPIView[Landmark], SDBAPIViewMixin):
    """API View for managing personal Points of Interest.

    POIs are personal/private - users can only see and modify their own POIs.
    - Shows only POIs created by the authenticated user
    - Requires authentication and ownership
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LandmarkSerializer
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[Landmark]:
        """Get only POIs created by the authenticated user."""
        user = self.get_user()
        return Landmark.objects.filter(user=user).select_related("user")

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return SuccessResponse({"pois": serializer.data})

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new POI for the authenticated user."""
        user = self.get_user()

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user)
            return SuccessResponse(
                {"poi": serializer.data},
                status=status.HTTP_201_CREATED,
            )

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class LandmarkGeoJSONView(GenericAPIView[Landmark], SDBAPIViewMixin):
    """
    View to get user's POIs as GeoJSON-compatible data.
    Used by the map viewer to display POI markers.
    Only shows POIs created by the authenticated user.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LandmarkGeoJSONSerializer

    def get_queryset(self) -> QuerySet[Landmark]:
        """Get only POIs created by the authenticated user."""
        user = self.get_user()
        return Landmark.objects.filter(user=user).select_related("user")

    def get(self, request: Request) -> Response:
        """Get user's POIs in a map-friendly format."""
        pois = self.get_queryset()

        # Use the map serializer to convert to GeoJSON format
        serializer = self.get_serializer(pois, many=True)
        features = serializer.data

        return SuccessResponse({"type": "FeatureCollection", "features": features})
