# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import orjson
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v2.permissions import IsReadOnly
from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.serializers import GPSTrackSerializer
from speleodb.gis.models import GPSTrack
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.gpx import GPX_CONTENT_TYPE
from speleodb.utils.gpx import InvalidGPSTrackGeoJSONError
from speleodb.utils.gpx import dated_export_filename
from speleodb.utils.gpx import gps_track_geojson_to_gpx
from speleodb.utils.gpx import gpx_download_response
from speleodb.utils.response import ErrorResponse

if TYPE_CHECKING:
    from django.http import StreamingHttpResponse
    from rest_framework.request import Request
    from rest_framework.response import Response


class GPSTrackExportGPXAPIView(GenericAPIView[GPSTrack], SDBAPIViewMixin):
    """Export one readable GPS Track as GPX 1.1."""

    queryset = GPSTrack.objects.filter(is_active=True)
    permission_classes = [IsReadOnly & SDB_ReadAccess]
    serializer_class = GPSTrackSerializer
    lookup_field = "id"

    @extend_schema(
        operation_id="v2_gps_track_export_gpx",
        responses={
            (200, GPX_CONTENT_TYPE): OpenApiTypes.BINARY,
            400: OpenApiTypes.OBJECT,
        },
    )
    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response | StreamingHttpResponse:
        gps_track = self.get_object()

        try:
            with gps_track.file.open("rb") as geojson_file:
                geojson = orjson.loads(geojson_file.read())
            gpx = gps_track_geojson_to_gpx(geojson, track_name=gps_track.name)
        except (orjson.JSONDecodeError, InvalidGPSTrackGeoJSONError) as error:
            return ErrorResponse(
                {"error": f"GPS Track cannot be exported: {error}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filename = dated_export_filename(
            prefix="gps_track",
            name=gps_track.name,
            extension="gpx",
            fallback="track",
        )
        return gpx_download_response(gpx=gpx, filename=filename)
