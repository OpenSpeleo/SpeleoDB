# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from rest_framework import permissions
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.serializers import GPSTrackSerializer
from speleodb.gis.models import GPSTrack
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from typing import Any

    from rest_framework.request import Request
    from rest_framework.response import Response


class UserGPSTracks(GenericAPIView[GPSTrack], SDBAPIViewMixin):
    """API view that returns raw GeoJSON data for every user's project."""

    queryset = GPSTrack.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GPSTrackSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Return all accessible projects and their GeoJSON data."""
        user = self.get_user()
        tracks = GPSTrack.objects.filter(user=user)

        serializer = self.get_serializer(tracks, many=True)
        return SuccessResponse(serializer.data)
