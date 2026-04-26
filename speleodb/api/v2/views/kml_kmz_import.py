# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import zipfile
from decimal import Decimal
from typing import TYPE_CHECKING
from typing import Any

import sentry_sdk
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from fastkml import KML
from fastkml.features import Placemark
from fastkml.features import _Feature as KML_Feature
from fastkml.geometry import Point
from openspeleo_lib.constants import OSPL_GEOJSON_DIGIT_PRECISION
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v2.landmark_access import user_has_collection_access
from speleodb.common.enums import PermissionLevel
from speleodb.gis.landmark_collections import get_or_create_personal_landmark_collection
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
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


def iter_points(
    feature: KML | KML_Feature,
) -> Generator[dict[str, str | Decimal]]:
    if isinstance(feature, Placemark):
        geom = feature.kml_geometry
        if isinstance(geom, Point):
            if geom.kml_coordinates is None:
                return

            for lon, lat, *_ in geom.kml_coordinates.coords:
                yield {
                    "name": feature.name or f"Imported on {timezone.now().isoformat()}",
                    "longitude": Decimal(str(round(lon, OSPL_GEOJSON_DIGIT_PRECISION))),
                    "latitude": Decimal(str(round(lat, OSPL_GEOJSON_DIGIT_PRECISION))),
                    "description": feature.description or "",
                }

    for child in getattr(feature, "features", []):
        yield from iter_points(child)


class KML_KMZ_ImportView(GenericAPIView[Project], SDBAPIViewMixin):  # noqa: N801
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
                "properties": {"landmarks_created": {"type": "integer"}},
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

        # ~~~~~~~~~~~~~~~~~~ START of parsing KML / KMZ file ~~~~~~~~~~~~~~~~~~ #

        landmarks_created = 0

        try:
            kml = load_kml_kmz(file=file)

            with transaction.atomic():
                for point_data in iter_points(kml):
                    # Skip if Landmark already exists.
                    _, created = Landmark.objects.get_or_create(
                        latitude=point_data["latitude"],
                        longitude=point_data["longitude"],
                        collection=collection,
                        defaults={
                            "created_by": user.email,
                            "name": point_data["name"],
                            "description": point_data["description"],
                        },
                    )
                    if created:
                        landmarks_created += 1

        except Exception as e:
            if settings.DEBUG:
                raise

            logger.exception("Error importing KML/KMZ file")
            sentry_sdk.capture_exception(e)
            return ErrorResponse(
                {"error": "There has been a problem importing the KML/KMZ file"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return SuccessResponse(data={"landmarks_created": landmarks_created})
