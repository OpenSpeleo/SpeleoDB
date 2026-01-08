# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import GPSTrackOwnershipPermission
from speleodb.api.v1.serializers import GPSTrackSerializer
from speleodb.api.v1.serializers import GPSTrackWithFileSerializer
from speleodb.gis.models import GPSTrack
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from typing import Any

    from rest_framework.request import Request
    from rest_framework.response import Response


class UserGPSTracks(GenericAPIView[GPSTrack], SDBAPIViewMixin):
    """API view that returns raw GeoJSON data for every user's project."""

    queryset = GPSTrack.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GPSTrackWithFileSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Return all accessible projects and their GeoJSON data."""
        user = self.get_user()
        tracks = GPSTrack.objects.filter(user=user)

        serializer = self.get_serializer(tracks, many=True)
        return SuccessResponse(serializer.data)


class GPSTrackSpecificAPIView(GenericAPIView[GPSTrack], SDBAPIViewMixin):
    """API View for managing personal GPS Tracks.

    GPS Tracks are personal/private - users can only see and modify
    their own GPS Tracks.
    - Shows only GPS Tracks created by the authenticated user
    - Requires authentication and ownership
    """

    queryset = GPSTrack.objects.all()
    permission_classes = [GPSTrackOwnershipPermission]
    serializer_class = GPSTrackSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get detailed GPS Track information (only if owned by user)."""
        gps_track = self.get_object()
        serializer = self.get_serializer(gps_track)
        return SuccessResponse(serializer.data)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._update(request=request, partial=True, **kwargs)

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._update(request=request, partial=False, **kwargs)

    def _update(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        """Update a GPS Track (only if owned by user)."""
        gps_track = self.get_object()

        serializer = self.get_serializer(gps_track, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete a GPS Track (only if owned by user)."""
        gps_track = self.get_object()
        gps_track_id = gps_track.id
        gps_track.file.delete(save=False)
        gps_track.delete()
        return SuccessResponse(
            {"message": f"GPS Track {gps_track_id} deleted successfully"}
        )
