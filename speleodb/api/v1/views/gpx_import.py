# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING
from typing import Any

import gpxpy
import orjson
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import IntegrityError
from django.utils import timezone
from geojson import Feature  # type: ignore[attr-defined]
from geojson import FeatureCollection  # type: ignore[attr-defined]
from geojson import LineString  # type: ignore[attr-defined]
from openspeleo_lib.constants import OSPL_GEOJSON_DIGIT_PRECISION
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.gis.models import GPSTrack
from speleodb.gis.models import Landmark
from speleodb.surveys.models import Format
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request


logger = logging.getLogger(__name__)


def handle_exception(
    exception: Exception,
    message: str,
    status_code: int,
    format_assoc: dict[Format, bool],
    project: Project,
) -> ErrorResponse:
    additional_errors = []
    # Cleanup created formats
    for f_obj, created in format_assoc.items():
        if created:
            try:
                f_obj.delete()
            except Exception:  # noqa: BLE001
                additional_errors.append(
                    "Error during removal of created new format association"
                )

    # Reset project state
    try:
        project.git_repo.reset_and_remove_untracked()
    except Exception:  # noqa: BLE001
        additional_errors.append(
            "Error during resetting of the project to HEAD and removal of untracked "
            "files."
        )

    error_msg = message.format(exception)

    if additional_errors:
        error_msg += " - Additional Errors During Exception Handling: "
        error_msg += ", ".join(additional_errors)

    return ErrorResponse({"error": error_msg}, status=status_code)


class GPXImportView(GenericAPIView[Project], SDBAPIViewMixin):
    permission_classes = [permissions.IsAuthenticated]

    def put(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> SuccessResponse | ErrorResponse:
        user = self.get_user()

        # ~~~~~~~~~~~~~~~~~~ START of Form Data Validation ~~~~~~~~~~~~~~~~~~ #
        try:
            files = request.FILES.getlist("file")
        except KeyError:
            return ErrorResponse(
                {"error": "Uploaded file(s) `artifact` is/are missing."},
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
                        f"[{file.size / 1024.0 / 1204.0} Mb], exceeds the limit: "
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

        landmarks_created = 0
        gps_tracks_created = 0

        # ~~~~~~~~~~~~~~~~~ START of writing files to project ~~~~~~~~~~~~~~~~~ #
        try:
            with file.open(mode="r") as f:
                gpx = gpxpy.parse(f)

            # 1. First let's extract the Waypoints and convert them to Landmarks
            for waypoint in gpx.waypoints:
                ldmk, created = Landmark.objects.get_or_create(
                    latitude=waypoint.latitude,
                    longitude=waypoint.longitude,
                    user=user,
                )
                if created:
                    ldmk.name = (
                        waypoint.name or f"Imported on {timezone.now().isoformat()}"
                    )
                    ldmk.save(update_fields=["name"])
                    landmarks_created += 1

            # 2. Let's extract the track and convert them to individual GPSTrack\
            for track in gpx.tracks:
                features = []
                track_data = {slot: getattr(track, slot) for slot in track.__slots__}
                del track_data["segments"]
                del track_data["extensions"]

                for seg_id, segment in enumerate(track.segments):
                    track_list = [
                        (point.longitude, point.latitude, int(point.elevation))
                        if point.elevation
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

                with contextlib.suppress(IntegrityError, ValidationError):
                    _ = GPSTrack.objects.create(
                        name=track.name or f"Imported on {timezone.now().isoformat()}",
                        file=geojson_f,
                        user=user,
                    )
                    gps_tracks_created += 1

        except Exception as e:
            if settings.DEBUG:
                raise

            return ErrorResponse(
                f"There has been a problem converting the GPX file: {e}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return SuccessResponse(
            data={
                "landmarks_created": landmarks_created,
                "gps_tracks_created": gps_tracks_created,
            }
        )
