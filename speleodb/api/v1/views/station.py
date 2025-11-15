# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.db import IntegrityError
from django.db.models.query import QuerySet
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import IsObjectCreation
from speleodb.api.v1.permissions import IsObjectDeletion
from speleodb.api.v1.permissions import IsObjectEdition
from speleodb.api.v1.permissions import IsReadOnly
from speleodb.api.v1.permissions import ProjectUserHasReadAccess
from speleodb.api.v1.permissions import StationUserHasAdminAccess
from speleodb.api.v1.permissions import StationUserHasReadAccess
from speleodb.api.v1.permissions import StationUserHasWriteAccess
from speleodb.api.v1.serializers.station import StationGeoJSONSerializer
from speleodb.api.v1.serializers.station import StationSerializer
from speleodb.api.v1.serializers.station import StationWithResourcesSerializer
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Station
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.compat import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response
    from rest_framework.serializers import ModelSerializer


class BaseStationsApiView(GenericAPIView[Station], SDBAPIViewMixin):
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
        return Station.objects.filter(project__in=user_projects)


class StationsApiView(BaseStationsApiView):
    """
    Simple view to get all stations that belongs to a user.
    """

    serializer_class = StationSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        stations = self.get_queryset()
        serializer = self.get_serializer(stations, many=True)
        return SuccessResponse(serializer.data)


class StationsGeoJSONApiView(BaseStationsApiView):
    """
    Simple view to get all stations for a user as GeoJSON-compatible data.
    Used by the map viewer to display station markers.
    """

    serializer_class = StationGeoJSONSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get all stations for a user in a map-friendly format."""
        stations = self.get_queryset()
        serializer = self.get_serializer(stations, many=True)

        return SuccessResponse(
            {"type": "FeatureCollection", "features": serializer.data}
        )


class StationSpecificApiView(GenericAPIView[Station], SDBAPIViewMixin):
    queryset = Station.objects.all()
    permission_classes = [
        (IsObjectDeletion & StationUserHasAdminAccess)
        | (IsObjectEdition & StationUserHasWriteAccess)
        | (IsReadOnly & StationUserHasReadAccess)
    ]
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        station = self.get_object()
        serializer = StationWithResourcesSerializer(station)

        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        station = self.get_object()
        serializer = StationSerializer(station, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._modify_obj(request=request, partial=True, **kwargs)

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

    def get_serializer_class(self) -> type[ModelSerializer[Station]]:  # type: ignore[override]
        if self.request.method == "GET":
            return StationWithResourcesSerializer
        return StationSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get all stations that belong to the project."""
        project = self.get_object()
        serializer = StationWithResourcesSerializer(
            project.rel_stations.all(),
            many=True,
        )
        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new station for the project."""
        project = self.get_object()
        user = self.get_user()

        serializer = StationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save(created_by=user.email, project=project)
            except IntegrityError:
                return ErrorResponse(
                    {
                        "error": (
                            f"The station name `{serializer.data['name']}` already "
                            f"exists in project `{project.id}`"
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return SuccessResponse(
                serializer.data,
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
    permission_classes = [ProjectUserHasReadAccess]
    lookup_field = "id"
    serializer_class = StationGeoJSONSerializer  # type: ignore[assignment]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get all stations for a project in a map-friendly format."""
        project = self.get_object()

        stations = Station.objects.filter(project=project)

        serializer = self.get_serializer(stations, many=True)

        return SuccessResponse(
            {"type": "FeatureCollection", "features": serializer.data}
        )
