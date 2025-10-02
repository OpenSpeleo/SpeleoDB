# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.db.models.query import QuerySet
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import IsObjectCreation
from speleodb.api.v1.permissions import IsObjectDeletion
from speleodb.api.v1.permissions import IsObjectEdition
from speleodb.api.v1.permissions import IsReadOnly
from speleodb.api.v1.permissions import StationUserHasAdminAccess
from speleodb.api.v1.permissions import StationUserHasReadAccess
from speleodb.api.v1.permissions import StationUserHasWriteAccess
from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.serializers.station import StationGeoJSONSerializer
from speleodb.api.v1.serializers.station import StationSerializer
from speleodb.surveys.models import Project
from speleodb.surveys.models import Station
from speleodb.surveys.models.permission_lvl import PermissionLevel
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.compat import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response


class StationsApiView(GenericAPIView[Station], SDBAPIViewMixin):
    """
    Simple view to get all stations that belongs to a user or create a station.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self) -> QuerySet[Station]:
        """Get only stations that the user has access to."""
        user = self.get_user()
        user_projects: list[Project] = [
            perm.project
            for perm in user.permissions
            if perm.level >= PermissionLevel.READ_ONLY
        ]
        return Station.objects.filter(project__in=user_projects).select_related(
            "created_by"
        )

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        stations = self.get_queryset()
        serializer = StationSerializer(stations, many=True)
        return SuccessResponse({"stations": serializer.data})


class StationSpecificApiView(GenericAPIView[Station], SDBAPIViewMixin):
    queryset = Station.objects.all().select_related("created_by")
    permission_classes = [
        (IsObjectDeletion & StationUserHasAdminAccess)
        | (IsObjectEdition & StationUserHasWriteAccess)
        | (IsReadOnly & StationUserHasReadAccess)
    ]
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        station = self.get_object()
        serializer = StationSerializer(station)

        return SuccessResponse(serializer.data)

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        station = self.get_object()
        serializer = StationSerializer(station, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        station = self.get_object()
        serializer = StationSerializer(station, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        station = self.get_object()

        # Backup object `id` before deletion
        station_id = station.id

        # Delete object itself
        station.delete()

        return SuccessResponse({"id": str(station_id)})


class ProjectStationsApiView(GenericAPIView[Project], SDBAPIViewMixin):
    """
    Simple view to get all stations that belongs to a user or create a station.
    """

    queryset = Project.objects.all()
    permission_classes = [
        (IsObjectCreation & StationUserHasWriteAccess)
        | (IsReadOnly & StationUserHasReadAccess)
    ]
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get all stations that belong to the project."""
        project = self.get_object()
        serializer = StationSerializer(
            project.rel_stations.all().select_related("created_by"),
            many=True,
        )
        return SuccessResponse({"stations": serializer.data})

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new station for the project."""
        project = self.get_object()
        # request.data["project"] = project
        serializer = StationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user, project=project)
            return SuccessResponse(
                {"station": serializer.data},
                status=status.HTTP_201_CREATED,
            )

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ProjectStationsGeoJSONView(GenericAPIView[Project], SDBAPIViewMixin):
    """
    Simple view to get all stations for a project as GeoJSON-compatible data.
    Used by the map viewer to display station markers.
    """

    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get all stations for a project in a map-friendly format."""
        project = self.get_object()

        stations = Station.objects.filter(project=project).select_related("created_by")

        serializer = StationGeoJSONSerializer(stations, many=True)

        return SuccessResponse(
            {"type": "FeatureCollection", "features": serializer.data}
        )
