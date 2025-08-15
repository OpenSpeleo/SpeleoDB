# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework import status
from rest_framework.parsers import FormParser
from rest_framework.parsers import JSONParser
from rest_framework.parsers import MultiPartParser
from rest_framework.viewsets import ModelViewSet

from speleodb.api.v1.permissions import StationUserHasAdminAccess
from speleodb.api.v1.permissions import StationUserHasReadAccess
from speleodb.api.v1.permissions import StationUserHasWriteAccess
from speleodb.api.v1.serializers.station import StationResourceSerializer
from speleodb.surveys.models import Station
from speleodb.surveys.models import StationResource
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rest_framework.compat import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response


class StationResourceViewSet(ModelViewSet[StationResource], SDBAPIViewMixin):
    """
    ViewSet for managing station resources.

    Resources are accessed directly by their ID, not nested under stations.
    - List: Returns all resources the user has access to
    - Create: Requires station_id in request data
    - Retrieve/Update/Delete: Operates on resource directly

    Permissions are checked through the resource's station's project.
    """

    serializer_class = StationResourceSerializer
    permission_classes = [permissions.IsAuthenticated, StationUserHasReadAccess]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[StationResource, StationResource]:
        """Get all resources the user has access to."""
        # Start with all resources
        queryset = StationResource.objects.all()

        # Could filter by user's accessible projects if needed
        # For now, permissions are checked in the views
        return queryset.select_related("station", "station__project")

    def get_permissions(  # type: ignore[override]
        self,
    ) -> list[permissions.BasePermission]:
        """Set permissions based on action."""
        match self.action:
            case "create" | "update" | "partial_update":
                return [permissions.IsAuthenticated(), StationUserHasWriteAccess()]

            case "destroy":
                return [permissions.IsAuthenticated(), StationUserHasAdminAccess()]

            case _:
                return [permissions.IsAuthenticated(), StationUserHasReadAccess()]

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get detailed resource information."""
        resource = self.get_object()

        # Check permissions against the resource's station's project
        self.check_object_permissions(request, resource.station.project)

        serializer = self.get_serializer(resource)
        return SuccessResponse({"resource": serializer.data})

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List all resources the user has access to."""
        # If station_id is provided as query param, filter by that station
        station_id = request.query_params.get("station_id")
        if station_id:
            station = get_object_or_404(Station, id=station_id)
            self.check_object_permissions(request, station.project)
            queryset = self.get_queryset().filter(station=station)
        else:
            # For general list, we would need to filter by user's accessible projects
            # For now, just return empty to avoid permission issues
            return SuccessResponse({"resources": []})

        serializer = self.get_serializer(queryset, many=True)
        return SuccessResponse({"resources": serializer.data})

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new resource."""
        # Get station_id from request data
        station_id = request.data.get("station_id")
        if not station_id:
            return ErrorResponse(
                {"errors": {"station_id": ["This field is required."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the station and check permissions
        station = get_object_or_404(Station, id=station_id)
        self.check_object_permissions(request, station.project)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                # Save with the station and created_by
                resource = serializer.save(station=station, created_by=request.user)
                return SuccessResponse(
                    {"resource": self.get_serializer(resource).data},
                    status=status.HTTP_201_CREATED,
                )

            except ValidationError as e:
                # Convert model validation errors to API format
                errors: Mapping[str, Any] = {}
                if hasattr(e, "error_dict"):
                    errors = e.error_dict
                elif hasattr(e, "error_list"):
                    errors = {"non_field_errors": e.error_list}
                else:
                    errors = {"non_field_errors": [str(e)]}

                # Convert ErrorList to list of strings
                for field, error_list in errors.items():
                    errors[field] = [str(error) for error in error_list]  # type: ignore[misc]

                return ErrorResponse(
                    {"errors": errors}, status=status.HTTP_400_BAD_REQUEST
                )

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Update a resource."""
        partial = kwargs.pop("partial", False)
        resource = self.get_object()

        # Check permissions against the resource's station's project
        self.check_object_permissions(request, resource.station.project)

        serializer = self.get_serializer(resource, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse({"resource": serializer.data})
        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete a resource."""
        resource = self.get_object()

        # Check permissions against the resource's station's project
        self.check_object_permissions(request, resource.station.project)

        resource_id = resource.id

        # Delete associated file if it exists
        if resource.file:
            resource.file.delete(save=False)

        resource.delete()
        return SuccessResponse(
            {"message": f"Resource {resource_id} deleted successfully"}
        )
