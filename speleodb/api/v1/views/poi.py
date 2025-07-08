# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.viewsets import ModelViewSet

from speleodb.api.v1.permissions import POIOwnershipPermission
from speleodb.api.v1.serializers.poi import PointOfInterestListSerializer
from speleodb.api.v1.serializers.poi import PointOfInterestMapSerializer
from speleodb.api.v1.serializers.poi import PointOfInterestSerializer
from speleodb.surveys.models import PointOfInterest
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response


class PointOfInterestViewSet(ModelViewSet[PointOfInterest], SDBAPIViewMixin):
    """
    ViewSet for managing Points of Interest.

    POIs are personal/private - users can only see and modify their own POIs.
    - List/Retrieve: Shows only POIs created by the authenticated user
    - Create/Update/Delete: Requires authentication and ownership
    """

    serializer_class = PointOfInterestSerializer
    permission_classes = [POIOwnershipPermission]
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[PointOfInterest]:
        """Get only POIs created by the authenticated user."""
        user = self.get_user()
        return PointOfInterest.objects.filter(created_by=user).select_related(
            "created_by"
        )

    def get_serializer_class(self) -> type[Any]:
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return PointOfInterestListSerializer
        return PointOfInterestSerializer

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List POIs created by the authenticated user."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return SuccessResponse({"pois": serializer.data})

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get detailed POI information (only if owned by user)."""
        poi = self.get_object()
        serializer = self.get_serializer(poi)
        return SuccessResponse({"poi": serializer.data})

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new POI for the authenticated user."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            poi = serializer.save(created_by=request.user)
            return SuccessResponse(
                {"poi": self.get_serializer(poi).data},
                status=status.HTTP_201_CREATED,
            )
        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Update a POI (only if owned by user)."""
        partial = kwargs.pop("partial", False)
        poi = self.get_object()

        serializer = self.get_serializer(poi, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            # Refresh from DB to get updated relations
            poi.refresh_from_db()
            return SuccessResponse({"poi": self.get_serializer(poi).data})
        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete a POI (only if owned by user)."""
        poi = self.get_object()
        poi_id = poi.id
        poi.delete()
        return SuccessResponse(
            {"message": f"Point of Interest {poi_id} deleted successfully"}
        )


class PointOfInterestMapView(GenericAPIView[PointOfInterest], SDBAPIViewMixin):
    """
    View to get user's POIs as GeoJSON-compatible data.
    Used by the map viewer to display POI markers.
    Only shows POIs created by the authenticated user.
    """

    permission_classes = [POIOwnershipPermission]
    serializer_class = PointOfInterestMapSerializer

    def get(self, request: Request) -> Response:
        """Get user's POIs in a map-friendly format."""
        user = self.get_user()
        pois = PointOfInterest.objects.filter(created_by=user).select_related(
            "created_by"
        )

        # Use the map serializer to convert to GeoJSON format
        serializer = self.get_serializer(pois, many=True)
        features = serializer.data

        return SuccessResponse({"type": "FeatureCollection", "features": features})
