# -*- coding: utf-8 -*-

"""Abstract base classes for the OGC API - Features endpoint hierarchy.

Every OGC endpoint pair (GIS-View and User) shares identical protocol
logic.  The *only* things that change between the two are:

* The Django model and lookup field used to authenticate/authorize the
  request (``GISView`` / ``gis_token`` vs ``Token`` / ``key``).
* How the list of ``ProjectGeoJSON`` objects is obtained.

This module defines one abstract base class per OGC endpoint type.
Concrete subclasses in ``gis_view.py`` and ``project_geojson.py``
are 3-10 lines each: they set ``queryset`` / ``lookup_field`` and
implement the single abstract getter.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING
from typing import Any

import orjson
from django.core.cache import cache
from django.http import HttpResponseNotModified
from django.http import StreamingHttpResponse
from geojson import FeatureCollection  # type: ignore[attr-defined]
from rest_framework import permissions
from rest_framework.generics import GenericAPIView

from speleodb.gis.ogc_models import OGCLayerList
from speleodb.gis.ogc_models import build_ogc_conformance
from speleodb.gis.ogc_models import build_ogc_landing_page
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import NoWrapResponse

if TYPE_CHECKING:
    from rest_framework.request import Request

    from speleodb.gis.models import ProjectGeoJSON

# ---------------------------------------------------------------------------
# GeoJSON proxy helper
# ---------------------------------------------------------------------------
# Cache timeout: 24 hours.  Content is immutable (tied to a git commit SHA)
# so this is actually conservative — the data can never change for a given key.
_GEOJSON_CACHE_TIMEOUT: int = 60 * 60 * 24


def serve_geojson_proxy(
    project_geojson: ProjectGeoJSON,
    request: Request,
) -> StreamingHttpResponse | HttpResponseNotModified:
    """Serve a filtered GeoJSON FeatureCollection with caching and ETag support.

    Behaviour
    ---------
    * **LineString filter** — only ``LineString`` features are included so that
      QGIS (which requires a single geometry type per layer) renders correctly.
    * **Immutable cache** — the filtered result is cached under
      ``ogc_geojson_{commit_sha}`` for 24 h.  Because the content is tied to
      a git commit SHA it can never change, so every request after the first
      one is served from cache without hitting S3.
    * **ETag / 304** — the commit SHA is used as an ``ETag``.  If the client
      sends ``If-None-Match`` with a matching value, a ``304 Not Modified``
      is returned with zero body bytes.
    * **StreamingHttpResponse** — required so that
      ``DRFWrapResponseMiddleware`` skips this response (plain
      ``HttpResponse`` would be wrapped in a JSON envelope, breaking GeoJSON
      consumers).
    * All query parameters (``limit``, ``bbox``, ``filter`` …) sent by QGIS
      are silently ignored — the full dataset is always returned.
    """
    commit_sha: str = project_geojson.commit_sha
    etag = f'"{commit_sha}"'

    # HTTP conditional request — return 304 if client already has this version
    if request.headers.get("if-none-match") == etag:
        response_nm: HttpResponseNotModified = HttpResponseNotModified()
        response_nm["ETag"] = etag
        return response_nm

    # Try Django cache first (Redis in production, LocMemCache in dev)
    cache_key = f"ogc_geojson_{commit_sha}"
    content: bytes | None = cache.get(cache_key)

    if content is None:
        # Read from S3 and filter to LineString features only
        with project_geojson.file.open("rb") as f:
            features = orjson.loads(f.read()).get("features", [])

        filtered = FeatureCollection(  # type: ignore[no-untyped-call]
            [
                feature
                for feature in features
                if feature.get("geometry", {}).get("type") == "LineString"
            ]
        )
        content = orjson.dumps(filtered)
        cache.set(cache_key, content, timeout=_GEOJSON_CACHE_TIMEOUT)

    response: StreamingHttpResponse = StreamingHttpResponse(
        streaming_content=[content],
        content_type="application/geo+json",
    )
    response["ETag"] = etag
    response["Cache-Control"] = "public, max-age=86400"
    response["Content-Disposition"] = "inline"
    return response


# ---------------------------------------------------------------------------
# Abstract base classes
# ---------------------------------------------------------------------------


class BaseOGCLandingPageApiView(GenericAPIView, SDBAPIViewMixin):  # type: ignore[type-arg]
    """OGC API - Features landing page.

    Returns links to conformance and collections endpoints so that
    GIS clients (QGIS, ArcGIS) can discover the service.

    Subclasses must set ``queryset`` and ``lookup_field``.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> NoWrapResponse:
        self.get_object()  # validate token / lookup (404 if invalid)
        return NoWrapResponse(build_ogc_landing_page(request=request))


class BaseOGCConformanceApiView(GenericAPIView, SDBAPIViewMixin):  # type: ignore[type-arg]
    """OGC API - Features conformance declaration.

    Subclasses must set ``queryset`` and ``lookup_field``.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> NoWrapResponse:
        self.get_object()  # validate token / lookup
        return NoWrapResponse(build_ogc_conformance())


class BaseOGCCollectionsApiView(GenericAPIView, SDBAPIViewMixin, abc.ABC):  # type: ignore[type-arg]
    """OGC API ``/collections`` endpoint.

    Subclasses must set ``queryset`` and ``lookup_field``, and implement
    :meth:`get_ogc_layer_data`.
    """

    permission_classes = [permissions.AllowAny]

    @abc.abstractmethod
    def get_ogc_layer_data(self) -> list[dict[str, Any]]:
        """
        Return a list of dicts with keys ``sha``, ``title``, ``description``, ``url``.
        """
        ...

    def get(self, request: Request, *args: Any, **kwargs: Any) -> NoWrapResponse:
        data: list[dict[str, Any]] = self.get_ogc_layer_data()
        ogc_layers: OGCLayerList = OGCLayerList.model_validate({"layers": data})
        return NoWrapResponse(ogc_layers.to_ogc_collections(request=request))


class BaseOGCCollectionApiView(GenericAPIView, SDBAPIViewMixin, abc.ABC):  # type: ignore[type-arg]
    """OGC API single-collection metadata endpoint.

    Subclasses must set ``queryset`` and ``lookup_field``, and implement
    :meth:`get_geojson_object`.
    """

    permission_classes = [permissions.AllowAny]

    @abc.abstractmethod
    def get_geojson_object(self, commit_sha: str) -> ProjectGeoJSON:
        """Fetch and authorize a ``ProjectGeoJSON`` for *commit_sha*."""
        ...

    def get(self, request: Request, *args: Any, **kwargs: Any) -> NoWrapResponse:
        commit_sha: str = kwargs["commit_sha"]
        project_geojson: ProjectGeoJSON = self.get_geojson_object(commit_sha)

        host = f"{request.scheme}://{request.get_host().rstrip('/')}"
        self_path: str = request.path.rstrip("/")

        return NoWrapResponse(
            {
                "id": project_geojson.commit_sha,
                "title": project_geojson.project.name,
                "description": f"Commit: {project_geojson.commit_sha}",
                "itemType": "feature",
                "links": [
                    {
                        "href": f"{host}{self_path}",
                        "rel": "self",
                        "type": "application/json",
                        "title": project_geojson.project.name,
                    },
                    {
                        "href": f"{host}{self_path}/items",
                        "rel": "items",
                        "type": "application/geo+json",
                        "title": f"{project_geojson.project.name} Items",
                    },
                ],
            }
        )


class BaseOGCCollectionItemApiView(GenericAPIView, SDBAPIViewMixin, abc.ABC):  # type: ignore[type-arg]
    """OGC API ``/items`` endpoint — serves filtered GeoJSON via proxy + cache.

    Subclasses must set ``queryset`` and ``lookup_field``, and implement
    :meth:`get_geojson_object`.
    """

    permission_classes = [permissions.AllowAny]

    @abc.abstractmethod
    def get_geojson_object(self, commit_sha: str) -> ProjectGeoJSON:
        """Fetch and authorize a ``ProjectGeoJSON`` for *commit_sha*."""
        ...

    def get(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> StreamingHttpResponse | HttpResponseNotModified:
        commit_sha: str = kwargs["commit_sha"]
        project_geojson: ProjectGeoJSON = self.get_geojson_object(commit_sha)
        return serve_geojson_proxy(project_geojson, request)
