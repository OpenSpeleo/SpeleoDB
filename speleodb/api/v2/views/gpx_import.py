# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
from decimal import Decimal
from typing import TYPE_CHECKING
from typing import Any

import gpxpy
import orjson
import sentry_sdk
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import IntegrityError
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from geojson import Feature  # type: ignore[attr-defined]
from geojson import FeatureCollection  # type: ignore[attr-defined]
from geojson import LineString  # type: ignore[attr-defined]
from openspeleo_lib.constants import OSPL_GEOJSON_DIGIT_PRECISION
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v2.landmark_access import user_has_collection_access
from speleodb.common.enums import PermissionLevel
from speleodb.gis.landmark_collections import get_or_create_personal_landmark_collection
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request


logger = logging.getLogger(__name__)


class GPXImportView(GenericAPIView[Project], SDBAPIViewMixin):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
                "required": ["file"],
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "landmarks_created": {"type": "integer"},
                    "gps_tracks_created": {"type": "integer"},
                },
            }
        },
    )
    def put(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> SuccessResponse | ErrorResponse:
        user = self.get_user()
        collection_id = request.data.get("collection")
        if collection_id:
            try:
                collection = LandmarkCollection.objects.get(
                    id=collection_id,
                    is_active=True,
                )
            except LandmarkCollection.DoesNotExist, ValidationError, ValueError:
                return ErrorResponse(
                    {"error": "Landmark collection does not exist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not user_has_collection_access(
                user=user,
                collection=collection,
                min_level=PermissionLevel.READ_AND_WRITE,
            ):
                return ErrorResponse(
                    {
                        "error": (
                            "WRITE access is required to import landmarks into this "
                            "collection."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            collection = get_or_create_personal_landmark_collection(user=user)

        # ~~~~~~~~~~~~~~~~~~ START of Form Data Validation ~~~~~~~~~~~~~~~~~~ #
        files = request.FILES.getlist("file")
        if not files:
            return ErrorResponse(
                {"error": "Missing required `file` upload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify there's only one file
        if len(files) != 1:
            return ErrorResponse(
                {"error": f"Only one file expected, received: {len(files)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file = files[0]

        # Check if file size exceeds globally set limit
        if (
            file.size
            > settings.DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT * 1024 * 1024
        ):
            return ErrorResponse(
                {
                    "error": (
                        f"The file size for `{file.name}` "
                        f"[{file.size / 1024.0 / 1024.0} Mb], exceeds the limit: "
                        f"{settings.DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT} Mb"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check file type
        if not isinstance(file, (InMemoryUploadedFile, TemporaryUploadedFile)):
            return ErrorResponse(
                {"error": f"Unknown artifact received: `{file.name}`"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # ~~~~~~~~~~~~~~~~~~~~ END of Form Data Validation ~~~~~~~~~~~~~~~~~~~~ #

        # ~~~~~~~~~~~~~~~~~~~~~ START of parsing GPX file ~~~~~~~~~~~~~~~~~~~~~ #

        landmarks_created = 0
        gps_tracks_created = 0

        try:
            with file.open(mode="r") as f:
                gpx = gpxpy.parse(f)

            with transaction.atomic():
                # 1. First let's extract the Waypoints and convert them to Landmarks
                for waypoint in gpx.waypoints:
                    # Skip if Landmark already exists.
                    _, created = Landmark.objects.get_or_create(
                        latitude=Decimal(str(waypoint.latitude)),
                        longitude=Decimal(str(waypoint.longitude)),
                        collection=collection,
                        defaults={
                            "created_by": user.email,
                            "name": (
                                waypoint.name
                                or f"Imported on {timezone.now().isoformat()}"
                            ),
                            "description": waypoint.description or "",
                        },
                    )
                    if created:
                        landmarks_created += 1

                # 2. Let's extract the track and convert them to individual GPSTrack
                for track in gpx.tracks:
                    features = []
                    track_data = {
                        slot: getattr(track, slot) for slot in track.__slots__
                    }
                    del track_data["segments"]
                    del track_data["extensions"]

                    for seg_id, segment in enumerate(track.segments):
                        track_list = [
                            (point.longitude, point.latitude, int(point.elevation))
                            if point.elevation is not None
                            else (point.longitude, point.latitude)
                            for point in segment.points
                        ]

                        features.append(
                            Feature(  # type: ignore[no-untyped-call]
                                geometry=LineString(
                                    track_list,
                                    precision=OSPL_GEOJSON_DIGIT_PRECISION,
                                ),  # type: ignore[no-untyped-call]
                                properties=dict(
                                    segment_id=seg_id + 1,
                                    **{
                                        key: val
                                        for key, val in track_data.copy().items()
                                        if val
                                    },
                                ),
                            )
                        )

                    geojson_f = SimpleUploadedFile(
                        "track.geojson",
                        orjson.dumps(FeatureCollection(features=features)),  # type: ignore[no-untyped-call]
                        content_type="application/geo+json",
                    )

                    # Skip if GPSTrack already exists
                    with (
                        contextlib.suppress(IntegrityError, ValidationError),
                        transaction.atomic(),
                    ):
                        _, created = GPSTrack.objects.get_or_create(
                            file=geojson_f,
                            user=user,
                            defaults={
                                "name": (
                                    track.name
                                    or f"Imported on {timezone.now().isoformat()}"
                                ),
                            },
                        )
                        if created:
                            gps_tracks_created += 1

        except Exception as e:
            if settings.DEBUG:
                raise

            logger.exception("Error importing GPX file")
            sentry_sdk.capture_exception(e)
            return ErrorResponse(
                {"error": "There has been a problem importing the GPX file"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return SuccessResponse(
            data={
                "landmarks_created": landmarks_created,
                "gps_tracks_created": gps_tracks_created,
            }
        )
