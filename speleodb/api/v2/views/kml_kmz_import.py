# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import sentry_sdk
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser
from rest_framework.parsers import MultiPartParser

from speleodb.api.v2.landmark_access import user_has_collection_access
from speleodb.api.v2.serializers.gis_layer import safe_upload_filename
from speleodb.common.enums import PermissionLevel
from speleodb.gis.gis_layer_processing import GISLayerProcessingError
from speleodb.gis.gis_layer_processing import analyze_kml_kmz
from speleodb.gis.gis_layer_processing.common import calculate_bbox
from speleodb.gis.landmark_collections import get_or_create_personal_landmark_collection
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.requests import require_mapping_request_data
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from typing import BinaryIO

    from rest_framework.request import Request

    from speleodb.gis.gis_layer_processing.types import KMLAnalysis
    from speleodb.gis.gis_layer_processing.types import LandmarkCandidate

logger = logging.getLogger(__name__)

KML_UPLOAD_REQUEST: dict[str, Any] = {
    "multipart/form-data": {
        "type": "object",
        "properties": {"file": {"type": "string", "format": "binary"}},
        "required": ["file"],
    }
}
KML_INSPECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "source_format": {"type": "string", "enum": ["KML", "KMZ"]},
        "suggested_name": {"type": "string"},
        "source_placemarks": {"type": "integer"},
        "places": {
            "type": "object",
            "properties": {
                key: {"type": "integer"}
                for key in (
                    "eligible_placemarks",
                    "point_count",
                    "unique_coordinate_count",
                    "duplicate_coordinate_count",
                    "skipped_placemarks",
                )
            },
        },
        "overlay": {
            "type": "object",
            "properties": {
                key: {"type": "integer"}
                for key in (
                    "source_placemarks",
                    "feature_count",
                    "point_parts",
                    "line_parts",
                    "polygon_parts",
                )
            },
        },
        "warnings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "count": {"type": "integer"},
                    "modes": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["places", "overlay"]},
                    },
                },
            },
        },
    },
}
KML_IMPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "landmarks_created": {"type": "integer"},
        "landmarks_skipped": {"type": "integer"},
        "duplicates_in_file": {"type": "integer"},
        "collection_id": {"type": "string", "format": "uuid"},
        "bounds": {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 4,
            "maxItems": 4,
            "nullable": True,
        },
    },
}


def _analyze_request(request: Request) -> KMLAnalysis | ErrorResponse:
    files = request.FILES.getlist("file")
    if not files:
        return ErrorResponse(
            {"error": "Missing required `file` upload."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(files) != 1:
        return ErrorResponse(
            {"error": f"Only one file expected, received: {len(files)}."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    file = files[0]
    if not isinstance(file, (InMemoryUploadedFile, TemporaryUploadedFile)):
        return ErrorResponse(
            {"error": "Unknown upload received."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return analyze_kml_kmz(cast("BinaryIO", file), filename=file.name or "")


def _processing_error(exc: GISLayerProcessingError) -> ErrorResponse:
    logger.exception("KML/KMZ upload rejected during analysis")
    sentry_sdk.capture_exception(exc)
    return ErrorResponse(
        {"error": exc.user_message, "code": exc.code.value, "details": exc.details},
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def _unexpected_error(exc: Exception) -> ErrorResponse:
    logger.exception("Error importing KML/KMZ file")
    sentry_sdk.capture_exception(exc)
    return ErrorResponse(
        {"error": "There has been a problem importing the KML/KMZ file"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@method_decorator(transaction.non_atomic_requests, name="dispatch")
class KMLKMZInspectView(GenericAPIView[Landmark], SDBAPIViewMixin):
    """Describe both import outcomes without publishing or staging any data."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request=KML_UPLOAD_REQUEST,
        responses={200: KML_INSPECTION_SCHEMA, 422: OpenApiTypes.OBJECT},
    )
    def post(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> SuccessResponse | ErrorResponse:
        try:
            analysis = _analyze_request(request)
            if isinstance(analysis, ErrorResponse):
                return analysis
            filename = request.FILES["file"].name or "source"
            suggested_name = safe_upload_filename(
                PurePosixPath(filename.replace("\\", "/")).stem
            )
            return SuccessResponse(
                {
                    **analysis.inspection(),
                    "source_format": PurePosixPath(filename).suffix.lstrip(".").upper(),
                    "suggested_name": suggested_name,
                }
            )
        except GISLayerProcessingError as exc:
            return _processing_error(exc)
        except Exception as exc:
            if settings.DEBUG:
                raise
            return _unexpected_error(exc)


@method_decorator(transaction.non_atomic_requests, name="dispatch")
class KML_KMZ_ImportView(GenericAPIView[Landmark], SDBAPIViewMixin):  # noqa: N801
    """Import point-only placemarks into one writable Landmark Collection."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "format": "binary"},
                    "collection": {"type": "string", "format": "uuid"},
                },
                "required": ["file"],
            }
        },
        responses={200: KML_IMPORT_SCHEMA, 422: OpenApiTypes.OBJECT},
    )
    def put(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> SuccessResponse | ErrorResponse:
        user = self.get_user()
        request_data = require_mapping_request_data(request.data)
        collection_id = request_data.get("collection")
        collection: LandmarkCollection | None = None
        if collection_id:
            try:
                collection = LandmarkCollection.objects.get(
                    id=collection_id, is_active=True
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

        try:
            analysis = _analyze_request(request)
            if isinstance(analysis, ErrorResponse):
                return analysis
            if not analysis.landmark_candidates:
                return ErrorResponse(
                    {
                        "error": "This file has no point-only placemarks to import.",
                        "code": "KML_NO_ELIGIBLE_PLACES",
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            candidates: dict[tuple[Decimal, Decimal], LandmarkCandidate] = {}
            for candidate in analysis.landmark_candidates:
                coordinates = (
                    Decimal(str(candidate.latitude)),
                    Decimal(str(candidate.longitude)),
                )
                candidates.setdefault(coordinates, candidate)
            duplicates_in_file = len(analysis.landmark_candidates) - len(candidates)
            created_positions: list[list[float]] = []
            landmarks_skipped = 0
            fallback_name = f"Imported on {timezone.now().isoformat()}"
            with transaction.atomic():
                if collection is None:
                    collection = get_or_create_personal_landmark_collection(user=user)
                else:
                    # Recheck at publication after analysis may have taken time.
                    collection.refresh_from_db(fields=["is_active"])
                    if not user_has_collection_access(
                        user=user,
                        collection=collection,
                        min_level=PermissionLevel.READ_AND_WRITE,
                    ):
                        return ErrorResponse(
                            {"error": "WRITE access to this collection has changed."},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                for (latitude, longitude), candidate in candidates.items():
                    _, created = Landmark.objects.get_or_create(
                        latitude=latitude,
                        longitude=longitude,
                        collection=collection,
                        defaults={
                            "created_by": user.email,
                            "name": candidate.name or fallback_name,
                            "description": candidate.description,
                        },
                    )
                    if created:
                        created_positions.append(
                            [candidate.longitude, candidate.latitude]
                        )
                    else:
                        landmarks_skipped += 1
        except GISLayerProcessingError as exc:
            return _processing_error(exc)
        except Exception as exc:
            if settings.DEBUG:
                raise
            return _unexpected_error(exc)

        return SuccessResponse(
            {
                "landmarks_created": len(created_positions),
                "landmarks_skipped": landmarks_skipped,
                "duplicates_in_file": duplicates_in_file,
                "collection_id": str(collection.id),
                "bounds": calculate_bbox(created_positions),
            }
        )
