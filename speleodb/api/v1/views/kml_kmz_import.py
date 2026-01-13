# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import zipfile
from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.utils import timezone
from fastkml import KML
from fastkml.features import Placemark
from fastkml.features import _Feature as KML_Feature
from fastkml.geometry import Point
from openspeleo_lib.constants import OSPL_GEOJSON_DIGIT_PRECISION
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.gis.models import Landmark
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from collections.abc import Generator

    from rest_framework.request import Request


logger = logging.getLogger(__name__)


def load_kml_kmz(file: InMemoryUploadedFile | TemporaryUploadedFile) -> KML:
    if zipfile.is_zipfile(file):
        with zipfile.ZipFile(file) as zf:
            # Find the main KML file (usually 'doc.kml')
            for name in zf.namelist():
                if name.lower().endswith(".kml"):
                    return KML.from_string(zf.read(name), strict=False)  # type: ignore[arg-type]

    return KML.from_string(file.read(), strict=False)


def iter_points(feature: KML | KML_Feature) -> Generator[dict[str, str | float]]:
    if isinstance(feature, Placemark):
        geom = feature.kml_geometry
        if isinstance(geom, Point):
            if geom.kml_coordinates is None:
                return

            for lon, lat, *_ in geom.kml_coordinates.coords:
                yield {
                    "name": feature.name or f"Imported on {timezone.now().isoformat()}",
                    "longitude": round(lon, OSPL_GEOJSON_DIGIT_PRECISION),
                    "latitude": round(lat, OSPL_GEOJSON_DIGIT_PRECISION),
                    "description": feature.description or "",
                }

    for child in getattr(feature, "features", []):
        yield from iter_points(child)


class KML_KMZ_ImportView(GenericAPIView[Project], SDBAPIViewMixin):  # noqa: N801
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

        # ~~~~~~~~~~~~~~~~~~ START of parsing KML / KMZ file ~~~~~~~~~~~~~~~~~~ #

        landmarks_created = 0

        try:
            kml = load_kml_kmz(file=file)

            for point_data in iter_points(kml):
                # Skip if Landmark already exists.
                _, created = Landmark.objects.get_or_create(
                    latitude=point_data["latitude"],
                    longitude=point_data["longitude"],
                    user=user,
                    defaults={
                        "name": point_data["name"],
                        "description": point_data["description"],
                    },
                )
                if created:
                    landmarks_created += 1

        except Exception as e:
            if settings.DEBUG:
                raise

            return ErrorResponse(
                f"There has been a problem importing the KML/KMZ file: {e}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return SuccessResponse(data={"landmarks_created": landmarks_created})
