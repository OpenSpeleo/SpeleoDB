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
from speleodb.api.v1.permissions import SDB_AdminAccess
from speleodb.api.v1.permissions import SDB_ReadAccess
from speleodb.api.v1.permissions import SDB_WriteAccess
from speleodb.api.v1.serializers.station import StationGeoJSONSerializer
from speleodb.api.v1.serializers.station import StationSerializer
from speleodb.api.v1.serializers.station import StationWithResourcesSerializer
from speleodb.api.v1.serializers.station import SubSurfaceStationSerializer
from speleodb.api.v1.serializers.station import SubSurfaceStationWithResourcesSerializer
from speleodb.api.v1.serializers.station import SurfaceStationSerializer
from speleodb.api.v1.serializers.station import SurfaceStationWithResourcesSerializer
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Station
from speleodb.gis.models import SubSurfaceStation
from speleodb.gis.models import SurfaceMonitoringNetwork
from speleodb.gis.models import SurfaceMonitoringNetworkUserPermission
from speleodb.gis.models import SurfaceStation
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.compat import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response
    from rest_framework.serializers import ModelSerializer


class BaseStationsApiView(GenericAPIView[SubSurfaceStation], SDBAPIViewMixin):
    """
    Simple view to get all stations that belongs to a user or create a station.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self) -> QuerySet[SubSurfaceStation]:
        """Get only stations that the user has access to."""
        user = self.get_user()
        user_projects: list[Project] = [
            perm.project
            for perm in user.permissions
            if perm.level >= PermissionLevel.READ_ONLY
        ]
        return SubSurfaceStation.objects.filter(project__in=user_projects)


class StationsApiView(BaseStationsApiView):
    """
    Simple view to get all stations that belongs to a user.
    """

    serializer_class = StationSerializer  # type: ignore[assignment]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        stations = self.get_queryset()
        serializer = self.get_serializer(stations, many=True)
        return SuccessResponse(serializer.data)


class StationsGeoJSONApiView(BaseStationsApiView):
    """
    Simple view to get all stations for a user as GeoJSON-compatible data.
    Used by the map viewer to display station markers.
    """

    serializer_class = StationGeoJSONSerializer  # type: ignore[assignment]

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
        (IsObjectDeletion & SDB_AdminAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
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
        (IsObjectCreation & SDB_WriteAccess) | (IsReadOnly & SDB_ReadAccess)
    ]
    lookup_field = "id"

    def get_serializer_class(self) -> type[ModelSerializer[SubSurfaceStation]]:  # type: ignore[override]
        if self.request.method == "GET":
            return SubSurfaceStationWithResourcesSerializer
        return SubSurfaceStationSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get all stations that belong to the project."""
        project = self.get_object()
        serializer = SubSurfaceStationWithResourcesSerializer(
            project.stations.all(),
            many=True,
        )
        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new station for the project."""
        project = self.get_object()
        user = self.get_user()

        serializer = SubSurfaceStationSerializer(data=request.data)
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
    permission_classes = [SDB_ReadAccess]
    lookup_field = "id"
    serializer_class = StationGeoJSONSerializer  # type: ignore[assignment]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get all stations for a project in a map-friendly format."""
        project = self.get_object()

        stations = SubSurfaceStation.objects.filter(project=project)

        serializer = self.get_serializer(stations, many=True)

        return SuccessResponse(
            {"type": "FeatureCollection", "features": serializer.data}
        )


# ================ SURFACE STATION VIEWS ================ #


class BaseSurfaceStationsApiView(GenericAPIView[SurfaceStation], SDBAPIViewMixin):
    """
    Base view for getting all surface stations that a user has access to.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self) -> QuerySet[SurfaceStation]:
        """Get only surface stations that the user has access to via network
        permissions."""
        user = self.get_user()
        # Get all networks where user has at least READ_ONLY access
        user_networks = [
            perm.network
            for perm in SurfaceMonitoringNetworkUserPermission.objects.filter(
                user=user,
                is_active=True,
                level__gte=PermissionLevel.READ_ONLY,
            )
        ]
        return SurfaceStation.objects.filter(network__in=user_networks)


class SurfaceStationsApiView(BaseSurfaceStationsApiView):
    """
    Simple view to get all surface stations that a user has access to.
    """

    serializer_class = StationSerializer  # type: ignore[assignment]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        stations = self.get_queryset()
        serializer = self.get_serializer(stations, many=True)
        return SuccessResponse(serializer.data)


class SurfaceStationsGeoJSONApiView(BaseSurfaceStationsApiView):
    """
    Simple view to get all surface stations for a user as GeoJSON-compatible data.
    Used by the map viewer to display station markers.
    """

    serializer_class = StationGeoJSONSerializer  # type: ignore[assignment]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get all surface stations for a user in a map-friendly format."""
        stations = self.get_queryset()
        serializer = self.get_serializer(stations, many=True)

        return SuccessResponse(
            {"type": "FeatureCollection", "features": serializer.data}
        )


class NetworkStationsApiView(GenericAPIView[SurfaceMonitoringNetwork], SDBAPIViewMixin):
    """
    View to get all stations for a network or create a new station.
    """

    queryset = SurfaceMonitoringNetwork.objects.all()
    permission_classes = [
        (IsObjectCreation & SDB_WriteAccess) | (IsReadOnly & SDB_ReadAccess)
    ]
    lookup_field = "id"
    lookup_url_kwarg = "network_id"

    def get_serializer_class(self) -> type[ModelSerializer[SurfaceStation]]:  # type: ignore[override]
        if self.request.method == "GET":
            return SurfaceStationWithResourcesSerializer
        return SurfaceStationSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get all stations that belong to the network."""
        network = self.get_object()
        serializer = SurfaceStationWithResourcesSerializer(
            network.stations.all(),
            many=True,
        )
        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new station for the network."""
        network = self.get_object()
        user = self.get_user()

        serializer = SurfaceStationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save(created_by=user.email, network=network)
            except IntegrityError:
                return ErrorResponse(
                    {
                        "error": (
                            f"The station name `{serializer.data['name']}` already "
                            f"exists in network `{network.id}`"
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


class NetworkStationsGeoJSONView(
    GenericAPIView[SurfaceMonitoringNetwork], SDBAPIViewMixin
):
    """
    View to get all stations for a network as GeoJSON-compatible data.
    Used by the map viewer to display station markers.
    """

    queryset = SurfaceMonitoringNetwork.objects.all()
    permission_classes = [SDB_ReadAccess]
    lookup_field = "id"
    lookup_url_kwarg = "network_id"
    serializer_class = StationGeoJSONSerializer  # type: ignore[assignment]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get all stations for a network in a map-friendly format."""
        network = self.get_object()

        stations = SurfaceStation.objects.filter(network=network)

        serializer = self.get_serializer(stations, many=True)

        return SuccessResponse(
            {"type": "FeatureCollection", "features": serializer.data}
        )
