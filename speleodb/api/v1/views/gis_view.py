# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.serializers.gis_view import GISViewDataSerializer
from speleodb.gis.models import GISView
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response

logger = logging.getLogger(__name__)


class GISViewDataApiView(GenericAPIView[GISView], SDBAPIViewMixin):
    """
    Public read-only endpoint to retrieve GeoJSON URLs for a GIS view.

    This endpoint is accessible via token without authentication.
    Returns signed URLs to GeoJSON files for all projects in the view.

    Pattern: Similar to ExperimentGISApiView
    Usage: External GIS tools (QGIS, ArcGIS, etc.)

    Endpoint: GET /api/v1/gis/view/<token>/
    Query params:
        - expires_in: URL expiration in seconds (default: 3600, max: 86400)
    """

    queryset = GISView.objects.all()
    permission_classes = [permissions.AllowAny]
    lookup_field = "gis_token"

    def get_queryset(self) -> Any:
        """Only return active views with prefetched relations."""
        return GISView.objects.prefetch_related("rel_view_projects__project")

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Return GeoJSON signed URLs for the view."""

        gis_view = self.get_object()

        # Get signed URLs with optional expiration parameter
        expires_in = int(request.query_params.get("expires_in", 3600))

        # Limit expiration time (max 24 hours for security)
        expires_in = min(max(expires_in, 60), 86400)

        # Use serializer with expires_in in context
        try:
            serializer = GISViewDataSerializer(
                gis_view, context={"expires_in": expires_in}
            )
            return SuccessResponse(serializer.data)
        except Exception:
            logger.exception("Error generating GeoJSON URLs for view %s", gis_view.id)
            return ErrorResponse(
                {"error": "Failed to generate GeoJSON URLs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
