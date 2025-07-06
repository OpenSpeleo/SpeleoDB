# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.db import IntegrityError
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser
from rest_framework.parsers import JSONParser
from rest_framework.parsers import MultiPartParser
from rest_framework.viewsets import ModelViewSet

from speleodb.api.v1.permissions import StationUserHasReadAccess
from speleodb.api.v1.permissions import StationUserHasWriteAccess
from speleodb.api.v1.serializers.station import StationCreateSerializer
from speleodb.api.v1.serializers.station import StationListSerializer
from speleodb.api.v1.serializers.station import StationResourceSerializer
from speleodb.api.v1.serializers.station import StationSerializer
from speleodb.surveys.models import Project
from speleodb.surveys.models import Station
from speleodb.surveys.models import StationResource
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.compat import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response


class StationViewSet(ModelViewSet[Station], SDBAPIViewMixin):
    """
    ViewSet for managing stations.

    - List/Retrieve: Requires READ_ACCESS on station's project
    - Create/Update/Delete: Requires WRITE_ACCESS on station's project
    """

    serializer_class = StationSerializer
    permission_classes = [StationUserHasReadAccess]
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[Station, Station]:
        """Get stations, optionally filtered by project."""
        queryset = Station.objects.all()

        # Filter by project if provided as query parameter
        project_id = self.request.query_params.get("project_id")
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        return queryset

    def get_serializer_class(self) -> type[Any]:
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return StationListSerializer
        if self.action == "create":
            return StationCreateSerializer
        return StationSerializer

    def get_permissions(  # type: ignore[override]
        self,
    ) -> list[StationUserHasWriteAccess] | list[StationUserHasReadAccess]:
        """Set permissions based on action."""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [StationUserHasWriteAccess()]
        return [StationUserHasReadAccess()]

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List stations, optionally filtered by project."""
        # If filtering by project, check permissions on that project
        project_id = request.query_params.get("project_id")
        if project_id:
            project = get_object_or_404(Project, id=project_id)
            self.check_object_permissions(request, project)

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return SuccessResponse({"stations": serializer.data})

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get detailed station information including resources."""
        station = self.get_object()
        # Check permissions on the station's project
        self.check_object_permissions(request, station.project)

        serializer = self.get_serializer(station)
        return SuccessResponse({"station": serializer.data})

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new station."""
        # Get project_id from request body
        project_id = request.data.get("project_id")
        if not project_id:
            return ErrorResponse(
                {"errors": {"project_id": ["This field is required."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check permissions against the project
        project = get_object_or_404(Project, id=project_id)
        self.check_object_permissions(request, project)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                station = serializer.save(project=project, created_by=request.user)
                detail_serializer = StationSerializer(
                    station, context=self.get_serializer_context()
                )
                return SuccessResponse(
                    {"station": detail_serializer.data}, status=status.HTTP_201_CREATED
                )
            except IntegrityError as e:
                # Check if it's a duplicate name error
                if "unique constraint" in str(e).lower() and "name" in str(e).lower():
                    return ErrorResponse(
                        {
                            "errors": {
                                "name": [
                                    (
                                        f"A station with the name "
                                        f"'{request.data.get('name', '')}' already "
                                        "exists in this project."
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
        """Update a station."""
        partial = kwargs.pop("partial", False)
        station = self.get_object()

        # Check permissions on the station's current project
        self.check_object_permissions(request, station.project)

        # Check if project is being changed
        new_project_id = request.data.get("project_id")
        if new_project_id and str(new_project_id) != str(station.project.id):
            # Check permissions on the new project
            new_project = get_object_or_404(Project, id=new_project_id)
            self.check_object_permissions(request, new_project)

            # Check if a station with the same name exists in the new project
            station_name = request.data.get("name", station.name)
            if (
                Station.objects.filter(project=new_project, name=station_name)
                .exclude(id=station.id)
                .exists()
            ):
                return ErrorResponse(
                    {
                        "errors": {
                            "name": [
                                (
                                    f"A station with the name '{station_name}' already "
                                    "exists in the target project."
                                )
                            ]
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = self.get_serializer(station, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            # Refresh from DB to get updated relations
            station.refresh_from_db()
            detail_serializer = StationSerializer(
                station, context=self.get_serializer_context()
            )
            return SuccessResponse({"station": detail_serializer.data})
        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete a station and all its resources."""
        station = self.get_object()

        # Check permissions on the station's project
        self.check_object_permissions(request, station.project)

        station_id = station.id
        station.delete()
        return SuccessResponse(
            {"message": f"Station {station_id} deleted successfully"}
        )


class StationResourceViewSet(ModelViewSet[StationResource], SDBAPIViewMixin):
    """
    ViewSet for managing station resources.

    - List/Retrieve: Requires READ_ACCESS
    - Create/Update/Delete: Requires WRITE_ACCESS
    """

    serializer_class = StationResourceSerializer
    permission_classes = [StationUserHasReadAccess]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[StationResource, StationResource]:
        """Get resources for the specified station."""
        station_id = self.kwargs.get("station_id")
        station = get_object_or_404(Station, id=station_id)
        return StationResource.objects.filter(station=station)

    def get_permissions(  # type: ignore[override]
        self,
    ) -> list[StationUserHasWriteAccess] | list[StationUserHasReadAccess]:
        """Set permissions based on action."""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [StationUserHasWriteAccess()]
        return [StationUserHasReadAccess()]

    def get_serializer_context(self) -> dict[str, Any]:
        """Add station to serializer context."""
        context = super().get_serializer_context()
        station_id = self.kwargs.get("station_id")
        if station_id:
            context["station"] = get_object_or_404(Station, id=station_id)
        return context

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get detailed station resource information."""
        # Check permissions against the station's project
        station_id = self.kwargs.get("station_id")
        station = get_object_or_404(Station, id=station_id)
        self.check_object_permissions(request, station.project)

        resource = self.get_object()
        serializer = self.get_serializer(resource)
        return SuccessResponse({"resource": serializer.data})

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List all resources for a station."""
        # Check permissions against the station's project
        station_id = self.kwargs.get("station_id")
        station = get_object_or_404(Station, id=station_id)
        self.check_object_permissions(request, station.project)

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return SuccessResponse({"resources": serializer.data})

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new station resource."""
        # Check permissions against the station's project
        station_id = self.kwargs.get("station_id")
        station = get_object_or_404(Station, id=station_id)
        self.check_object_permissions(request, station.project)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Set the station and created_by
            station = self.get_serializer_context()["station"]
            resource = serializer.save(station=station, created_by=request.user)
            return SuccessResponse(
                {"resource": self.get_serializer(resource).data},
                status=status.HTTP_201_CREATED,
            )
        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Update a station resource."""
        # Check permissions against the station's project
        station_id = self.kwargs.get("station_id")
        station = get_object_or_404(Station, id=station_id)
        self.check_object_permissions(request, station.project)

        partial = kwargs.pop("partial", False)
        resource = self.get_object()
        serializer = self.get_serializer(resource, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse({"resource": serializer.data})
        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete a station resource."""
        # Check permissions against the station's project
        station_id = self.kwargs.get("station_id")
        station = get_object_or_404(Station, id=station_id)
        self.check_object_permissions(request, station.project)

        resource = self.get_object()
        resource_id = resource.id

        # Delete associated file if it exists
        if resource.file:
            resource.file.delete(save=False)

        resource.delete()
        return SuccessResponse(
            {"message": f"Resource {resource_id} deleted successfully"}
        )


class ProjectStationListView(GenericAPIView[Station], SDBAPIViewMixin):
    """
    Simple view to get all stations for a project as GeoJSON-compatible data.
    Used by the map viewer to display station markers.
    """

    permission_classes = [StationUserHasReadAccess]

    def get(self, request: Request) -> Response:
        """Get all stations for a project in a map-friendly format."""
        # Get project_id from query parameters
        project_id = request.query_params.get("project_id")
        if not project_id:
            return ErrorResponse(
                {"errors": {"project_id": ["This query parameter is required."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = get_object_or_404(Project, id=project_id)
        self.check_object_permissions(request, project)

        stations = Station.objects.filter(project=project).select_related("created_by")

        # Convert to GeoJSON-like format for easy map consumption
        station_features = []
        for station in stations:
            # Skip stations without valid coordinates
            if station.longitude is None or station.latitude is None:
                continue

            # Get resource count using direct query to avoid linter issues
            resource_count = StationResource.objects.filter(station=station).count()

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(station.longitude), float(station.latitude)],
                },
                "properties": {
                    "id": str(station.id),
                    "name": station.name,
                    "description": station.description,
                    "resource_count": resource_count,
                    "created_by": station.created_by.email
                    if station.created_by
                    else None,
                    "creation_date": station.creation_date.isoformat(),
                },
            }
            station_features.append(feature)

        return SuccessResponse(
            {"type": "FeatureCollection", "features": station_features}
        )
