# -*- coding: utf-8 -*-

"""OGC API - Features views scoped to a **GIS View** (``gis_token``).

The OGC base classes live in :mod:`speleodb.api.v1.views.ogc_base`.
Each concrete class below sets ``queryset`` / ``lookup_field`` and
implements the one abstract getter that specialises it for the
GIS-View workflow.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

from django.db.models import Q
from django.http import Http404
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import GISViewOwnershipPermission
from speleodb.api.v1.serializers.gis_view import GISViewDataSerializer
from speleodb.api.v1.serializers.gis_view import PublicGISViewSerializer
from speleodb.api.v1.views.ogc_base import BaseOGCCollectionApiView
from speleodb.api.v1.views.ogc_base import BaseOGCCollectionItemApiView
from speleodb.api.v1.views.ogc_base import BaseOGCCollectionsApiView
from speleodb.api.v1.views.ogc_base import BaseOGCConformanceApiView
from speleodb.api.v1.views.ogc_base import BaseOGCLandingPageApiView
from speleodb.gis.models import GISProjectView
from speleodb.gis.models import GISView
from speleodb.gis.models import ProjectGeoJSON
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private (authenticated) view endpoint — not OGC
# ---------------------------------------------------------------------------


class GISViewDataApiView(GenericAPIView[GISView], SDBAPIViewMixin):
    """Private read-only endpoint to retrieve GISView data.

    Query params:
        - expires_in: URL expiration in seconds (default: 3600, max: 86400)
    """

    queryset = GISView.objects.all()
    permission_classes = [GISViewOwnershipPermission]
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gis_view = self.get_object()

        expires_in = int(request.query_params.get("expires_in", 3600))
        expires_in = min(max(expires_in, 60), 86400)

        try:
            serializer = GISViewDataSerializer(
                gis_view,
                context={"expires_in": expires_in},
            )
            return SuccessResponse(serializer.data)

        except Exception:
            logger.exception("Error generating GeoJSON URLs for view %s", gis_view.id)
            return ErrorResponse(
                {"error": "Failed to generate GeoJSON URLs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ---------------------------------------------------------------------------
# OGC API - Features: GIS-View subclasses (public, token-based)
# ---------------------------------------------------------------------------


class OGCGISViewLandingPageApiView(BaseOGCLandingPageApiView):
    """OGC landing page for a GIS view."""

    queryset = GISView.objects.all()
    lookup_field = "gis_token"


class OGCGISViewConformanceApiView(BaseOGCConformanceApiView):
    """OGC conformance declaration for a GIS view."""

    queryset = GISView.objects.all()
    lookup_field = "gis_token"


class OGCGISViewCollectionsApiView(BaseOGCCollectionsApiView):
    """OGC ``/collections`` — lists projects in the view."""

    queryset = GISView.objects.all()
    lookup_field = "gis_token"

    def get_ogc_layer_data(self) -> list[dict[str, Any]]:
        gis_view: GISView = self.get_object()
        return [
            {
                "sha": d["project_geojson"].commit_sha,
                "title": d["project_name"],
                "description": f"Commit: {d['commit_sha']}",
                "url": d["project_geojson"].get_signed_download_url(expires_in=3600),
            }
            for d in gis_view.get_view_geojson_data()
        ]


class _GISViewCollectionMixin:
    """Shared ``get_geojson_object`` for the GIS-View collection endpoints."""

    def get_geojson_object(self, commit_sha: str) -> ProjectGeoJSON:
        gis_view: GISView = self.get_object()  # type: ignore[attr-defined]

        try:
            project_geojson = ProjectGeoJSON.objects.select_related(
                "project", "commit"
            ).get(commit__id=commit_sha)
        except ProjectGeoJSON.DoesNotExist as e:
            raise Http404(f"ProjectGeoJSON for commit '{commit_sha}' not found.") from e

        if (
            not GISProjectView.objects.filter(
                gis_view=gis_view,
                project=project_geojson.project,
            )
            .filter(Q(use_latest=True) | Q(commit_sha=commit_sha))
            .exists()
        ):
            raise Http404(f"Commit '{commit_sha}' not part of the specified GIS view.")

        return project_geojson


class OGCGISViewCollectionApiView(_GISViewCollectionMixin, BaseOGCCollectionApiView):
    """OGC single-collection metadata for a GIS-View project."""

    queryset = GISView.objects.all()
    lookup_field = "gis_token"


class OGCGISViewCollectionItemApiView(
    _GISViewCollectionMixin,
    BaseOGCCollectionItemApiView,
):
    """OGC ``/items`` — proxy-served filtered GeoJSON for a GIS-View project."""

    queryset = GISView.objects.all()
    lookup_field = "gis_token"


# ---------------------------------------------------------------------------
# Frontend map viewer endpoint (not OGC)
# ---------------------------------------------------------------------------


class PublicGISViewGeoJSONApiView(GenericAPIView[GISView], SDBAPIViewMixin):
    """Public endpoint returning GeoJSON URLs for the frontend map viewer.

    Usage: Public SpeleoDB map viewer at /view/<gis_token>/
    """

    queryset = GISView.objects.all()
    permission_classes = [permissions.AllowAny]
    lookup_field = "gis_token"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gis_view = self.get_object()
        serializer = PublicGISViewSerializer(
            gis_view,
            context={"expires_in": 3600},
        )
        return SuccessResponse(serializer.data)
