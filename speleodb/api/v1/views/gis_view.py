# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING
from typing import Any

import orjson
from django.core.cache import cache
from django.db.models import Q
from django.http import Http404
from django.http import StreamingHttpResponse
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import GISViewOwnershipPermission
from speleodb.api.v1.serializers.gis_view import GISViewDataSerializer
from speleodb.api.v1.serializers.gis_view import PublicGISViewSerializer
from speleodb.gis.models import GISProjectView
from speleodb.gis.models import GISView
from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.ogc_models import OGCLayerList
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import GISResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import Any

    from rest_framework.request import Request
    from rest_framework.response import Response


logger = logging.getLogger(__name__)


class GISViewDataApiView(GenericAPIView[GISView], SDBAPIViewMixin):
    """
    Private read-only endpoint to retrieve GISView data.

    Query params:
        - expires_in: URL expiration in seconds (default: 3600, max: 86400)
    """

    queryset = GISView.objects.all()
    permission_classes = [GISViewOwnershipPermission]
    lookup_field = "id"

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


class OGCGISViewDataApiView(GenericAPIView[GISView], SDBAPIViewMixin):
    """
    Public read-only endpoint to retrieve GeoJSON URLs for a GIS view.

    This endpoint is accessible via token without authentication.
    Returns signed URLs to GeoJSON files for all projects in the view.

    Pattern: Similar to ExperimentGISApiView
    Usage: External GIS tools (QGIS, ArcGIS, etc.)
    """

    queryset = GISView.objects.all()
    permission_classes = [permissions.AllowAny]
    lookup_field = "gis_token"

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> GISResponse:
        """Return GeoJSON signed URLs for the view."""

        gis_view = self.get_object()

        data = [
            {
                "sha": _data["project_geojson"].commit_sha,
                "title": _data["project_name"],
                "description": f"Commit: {_data['commit_sha']}",
                "url": _data["project_geojson"].get_signed_download_url(
                    expires_in=3600
                ),
            }
            for _data in gis_view.get_view_geojson_data()
        ]

        ogc_layers: OGCLayerList = OGCLayerList.model_validate({"layers": data})

        return GISResponse(ogc_layers.to_ogc_collections(request=request))


class BaseOGCGISViewCollectionApiView(GenericAPIView[GISView], SDBAPIViewMixin):
    queryset = GISView.objects.all()
    permission_classes = [permissions.AllowAny]
    lookup_field = "gis_token"

    def get_geojson_object(self, commit_sha: str) -> ProjectGeoJSON:
        gis_view = self.get_object()

        try:
            project_geojson = ProjectGeoJSON.objects.select_related(
                "project", "commit"
            ).get(commit__id=commit_sha)
        except ProjectGeoJSON.DoesNotExist as e:
            raise Http404(f"ProjectGeoJSON for commit '{commit_sha}' not found.") from e

        # Verify that the project_geojson is part of the gis_view
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


class OGCGISViewCollectionApiView(BaseOGCGISViewCollectionApiView):
    def get(
        self,
        request: Request,
        gis_token: str,
        commit_sha: str,
        *args: Any,
        **kwargs: Any,
    ) -> GISResponse:
        """Return GeoJSON signed URLs for the view."""
        project_geojson = self.get_geojson_object(commit_sha=commit_sha)

        return GISResponse(
            {
                "id": project_geojson.commit.id,
                "title": project_geojson.project.name,
                "description": f"Commit: {project_geojson.commit.id}",
                "itemType": "feature",
                "links": [
                    {
                        "href": project_geojson.get_signed_download_url(
                            expires_in=3600
                        ),
                        "rel": "items",
                        "type": "application/geo+json",
                        "title": f"{project_geojson.project.name}",
                    }
                ],
            }
        )


class OGCGISViewCollectionItemApiView(BaseOGCGISViewCollectionApiView):
    def get(
        self,
        request: Request,
        gis_token: str,
        commit_sha: str,
        *args: Any,
        **kwargs: Any,
    ) -> StreamingHttpResponse:
        project_geojson = self.get_geojson_object(commit_sha=commit_sha)

        buffer = BytesIO()

        cache_key = f"ogc_collections_project_geojson_{project_geojson.commit.id}"
        cached_content: bytes | None = cache.get(cache_key)

        if cached_content:
            buffer.write(cached_content)
            buffer.seek(0)  # rewind to start

        else:

            def geojson_filter() -> bytes:
                with project_geojson.file.open("rb") as f:
                    features = orjson.loads(f.read()).get("features", [])

                    data = {
                        "type": "FeatureCollection",
                        "features": [
                            feature
                            for feature in features
                            if feature.get("geometry", {}).get("type") == "LineString"
                        ],
                    }

                return orjson.dumps(data)

            data: bytes = geojson_filter()
            buffer.write(data)
            buffer.seek(0)  # rewind to start

            # set cache 1 hour
            cache.set(
                cache_key,
                data,
                timeout=60 * 60,
            )

        def buffer_stream() -> Generator[bytes, Any]:
            chunk_size = 4096
            while chunk := buffer.read(chunk_size):
                yield chunk

        return StreamingHttpResponse(
            buffer_stream(),
            content_type="application/geo+json",
        )


class PublicGISViewGeoJSONApiView(GenericAPIView[GISView], SDBAPIViewMixin):
    """
    Public endpoint returning GeoJSON URLs for frontend map viewer.

    This endpoint is accessible via gis_token without authentication.
    Returns signed URLs to GeoJSON files in a format suitable for the
    frontend map viewer (different from OGC format used by external GIS tools).

    Usage: Public SpeleoDB map viewer at /view/<gis_token>/
    """

    queryset = GISView.objects.all()
    permission_classes = [permissions.AllowAny]
    lookup_field = "gis_token"

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        """Return GeoJSON signed URLs for the view in frontend format."""

        gis_view = self.get_object()

        serializer = PublicGISViewSerializer(
            gis_view,
            context={"expires_in": 3600},
        )

        return SuccessResponse(serializer.data)
