# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.db import IntegrityError
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.viewsets import ModelViewSet

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


class PointOfInterestViewSet(ModelViewSet, SDBAPIViewMixin):
    """
    ViewSet for managing Points of Interest.

    - List/Retrieve: Public access (no authentication required)
    - Create/Update/Delete: Requires authentication
    """

    serializer_class = PointOfInterestSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[PointOfInterest]:
        """Get all POIs, ordered by name."""
        return PointOfInterest.objects.all().select_related("created_by")

    def get_serializer_class(self) -> type[Any]:
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return PointOfInterestListSerializer
        return PointOfInterestSerializer

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List all POIs."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return SuccessResponse({"pois": serializer.data})

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get detailed POI information."""
        poi = self.get_object()
        serializer = self.get_serializer(poi)
        return SuccessResponse({"poi": serializer.data})

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new POI."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                poi = serializer.save(created_by=request.user)
                return SuccessResponse(
                    {"poi": self.get_serializer(poi).data},
                    status=status.HTTP_201_CREATED,
                )
            except IntegrityError as e:
                # Check if it's a duplicate name error
                if "unique constraint" in str(e).lower() and "name" in str(e).lower():
                    return ErrorResponse(
                        {
                            "errors": {
                                "name": [
                                    (
                                        f"A Point of Interest with the name "
                                        f"'{request.data.get('name', '')}' already "
                                        "exists."
                                    )
                                ]
                            }
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Re-raise if it's a different integrity error
                raise
        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Update a POI."""
        partial = kwargs.pop("partial", False)
        poi = self.get_object()

        # Check if name is being changed and would cause a duplicate
        new_name = request.data.get("name", poi.name)
        if (
            new_name != poi.name
            and PointOfInterest.objects.filter(name=new_name)
            .exclude(id=poi.id)
            .exists()
        ):
            return ErrorResponse(
                {
                    "errors": {
                        "name": [
                            (
                                f"A Point of Interest with the name '{new_name}' "
                                "already exists."
                            )
                        ]
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

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
        """Delete a POI."""
        poi = self.get_object()
        poi_id = poi.id
        poi.delete()
        return SuccessResponse(
            {"message": f"Point of Interest {poi_id} deleted successfully"}
        )


class PointOfInterestMapView(GenericAPIView, SDBAPIViewMixin):
    """
    View to get all POIs as GeoJSON-compatible data.
    Used by the map viewer to display POI markers.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = PointOfInterestMapSerializer

    def get(self, request: Request) -> Response:
        """Get all POIs in a map-friendly format."""
        pois = PointOfInterest.objects.all().select_related("created_by")

        # Use the map serializer to convert to GeoJSON format
        serializer = self.get_serializer(pois, many=True)
        features = serializer.data

        return SuccessResponse({"type": "FeatureCollection", "features": features})
