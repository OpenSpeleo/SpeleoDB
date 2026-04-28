# -*- coding: utf-8 -*-

"""Generic OGC API - Features views and the ``OGCFeatureService`` interface.

The four OGC families served by SpeleoDB (project gis-view, project user
token, landmark single, landmark user) used to each have their own
landing/conformance/collections/collection/items implementations. Now
they all share a single set of generic views in this module; each family
is a ~60-line concrete :class:`OGCFeatureService` that the view binds to
via its ``service_class`` attribute. The compliance layer
(``links[rel=self]``, ``numberMatched``/``numberReturned``/``timeStamp``,
``crs``/``extent``/``storageCrs``, ``bbox``/``limit``/``datetime``
filtering, single-feature lookup) is implemented exactly once in
:mod:`speleodb.gis.ogc_helpers` and consumed by every family.

Subclassing pattern (3 lines per binding)::

    class OGCViewLandingPageApiView(BaseOGCLandingPageApiView):
        queryset = GISView.objects.all()
        lookup_field = "gis_token"
        service_class = ProjectViewOGCService

The ``BaseOGC*`` class names are preserved for import compatibility with
existing URL configurations during the migration.
"""

from __future__ import annotations

import abc
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

import orjson
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseNotModified
from django.http import StreamingHttpResponse
from django.utils.functional import cached_property
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.renderers import BaseRenderer
from rest_framework.renderers import JSONRenderer

from speleodb.gis.ogc_helpers import GEOMETRY_GROUPS_ORDERED
from speleodb.gis.ogc_helpers import absolute_url
from speleodb.gis.ogc_helpers import apply_ogc_query
from speleodb.gis.ogc_helpers import build_collection_metadata
from speleodb.gis.ogc_helpers import build_collections_response
from speleodb.gis.ogc_helpers import build_conformance_declaration
from speleodb.gis.ogc_helpers import build_items_envelope
from speleodb.gis.ogc_helpers import build_landing_page
from speleodb.gis.ogc_helpers import build_single_feature_response
from speleodb.gis.ogc_helpers import parse_ogc_query
from speleodb.gis.ogc_openapi import OGC_OPENAPI_BYTES
from speleodb.gis.ogc_openapi import OGC_OPENAPI_CACHE_CONTROL
from speleodb.gis.ogc_openapi import OGC_OPENAPI_CONTENT_TYPE
from speleodb.gis.ogc_openapi import OGC_OPENAPI_ETAG
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import NoWrapResponse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rest_framework.request import Request


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


class GeoJSONRenderer(BaseRenderer):
    """Declares ``application/geo+json`` so DRF content negotiation accepts it.

    OGC API Features Part 1 (RFC 7946) mandates this media type for the
    ``/items`` endpoint. Clients like ArcGIS Pro send
    ``Accept: application/geo+json``; without a matching renderer DRF
    rejects the request with 406 before the view method runs.

    The renderer is never used for actual serialisation — items views
    return a :class:`~django.http.StreamingHttpResponse` which bypasses
    DRF rendering entirely.
    """

    media_type: str = "application/geo+json"
    format: str = "geojson"

    def render(
        self,
        data: Any,
        accepted_media_type: str | None = None,
        renderer_context: Mapping[str, Any] | None = None,
    ) -> bytes:
        return orjson.dumps(data)


class LegacyGeoJSONRenderer(GeoJSONRenderer):
    """Accepts the non-standard ``application/geojson`` media type.

    Some clients use this variant instead of the RFC 7946 standard
    ``application/geo+json``.
    """

    media_type: str = "application/geojson"
    format: str = "geojson-legacy"


class OpenAPI30Renderer(BaseRenderer):
    """Declares ``application/vnd.oai.openapi+json`` for the service-desc.

    Strict OGC clients send ``Accept: application/vnd.oai.openapi+json``
    when fetching the API definition. Without a matching renderer DRF's
    content-negotiation step would 406 the request before our view's
    ``get`` method runs.

    The renderer is never used for actual serialisation — the view
    returns a :class:`~django.http.StreamingHttpResponse` of the
    pre-built bytes, which bypasses DRF rendering entirely.
    """

    media_type: str = "application/vnd.oai.openapi+json"
    format: str = "openapi-json"

    def render(
        self,
        data: Any,
        accepted_media_type: str | None = None,
        renderer_context: Mapping[str, Any] | None = None,
    ) -> bytes:
        return orjson.dumps(data)


# ---------------------------------------------------------------------------
# OGCFeatureService interface
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OGCCollectionMeta:
    """Lightweight metadata for a single OGC collection.

    Yielded by :meth:`OGCFeatureService.list_collections` and
    :meth:`OGCFeatureService.get_collection`. The generic view layer
    expands this into a full OGC collection document via
    :func:`speleodb.gis.ogc_helpers.build_collection_metadata`.

    The optional ``bbox`` carries the collection's 2-D spatial extent
    (``min_lon, min_lat, max_lon, max_lat``) so ``extent.spatial.bbox``
    on the response reflects real data instead of the world fallback.
    Services that can cheaply compute the bbox (project services do so
    from the cached features list; landmark services from a single
    aggregate query) populate it; everything else leaves it ``None``.
    """

    id: str
    title: str
    description: str = ""
    bbox: tuple[float, float, float, float] | None = None


class OGCFeatureService[ScopeT](abc.ABC):
    """Abstract OGC API - Features service.

    The four concrete subclasses (``ProjectViewOGCService``,
    ``ProjectUserOGCService``, ``LandmarkSingleOGCService``,
    ``LandmarkUserOGCService``) provide scope-aware data access. Generic
    views consume this interface to produce uniformly OGC-compliant
    responses.

    The type parameter ``ScopeT`` is the scope object resolved by the
    view's ``GenericAPIView.get_object()`` (e.g. ``GISView`` for the
    project view family, ``Token`` for user-token families,
    ``LandmarkCollection`` for landmark single).
    """

    #: Human-readable service name used in landing pages.
    service_title: ClassVar[str] = "SpeleoDB OGC API - Features"

    #: Human-readable service description used in landing pages.
    service_description: ClassVar[str] = (
        "OGC API - Features endpoint for SpeleoDB GIS data."
    )

    #: ``Cache-Control`` header to send on items responses. Project file
    #: data is immutable (keyed by commit SHA) so 24 h is safe; landmark
    #: data is mutable so subclasses override to a short revalidating
    #: value.
    cache_control: ClassVar[str] = "public, max-age=86400"

    @abc.abstractmethod
    def list_collections(self, scope: ScopeT) -> list[OGCCollectionMeta]:
        """Yield metadata for every collection visible through *scope*."""

    @abc.abstractmethod
    def get_collection(
        self,
        scope: ScopeT,
        collection_id: str,
    ) -> OGCCollectionMeta | None:
        """Return metadata for *collection_id* or ``None`` if not found."""

    @abc.abstractmethod
    def get_features(
        self,
        scope: ScopeT,
        collection_id: str,
    ) -> list[dict[str, Any]]:
        """Return the normalized feature list for *collection_id*.

        Implementations are responsible for any caching they want; the
        generic view never caches the result, so the service can apply
        commit-SHA-keyed cache for immutable data and live queries for
        mutable data.
        """

    def get_feature(
        self,
        scope: ScopeT,
        collection_id: str,
        feature_id: str,
    ) -> dict[str, Any] | None:
        """Return a single feature by id, or ``None`` if not found.

        Default implementation: linear scan of :meth:`get_features`.
        Subclasses may override for efficiency (e.g. landmarks can do an
        ORM lookup by primary key).
        """
        features = self.get_features(scope, collection_id)
        target = str(feature_id)
        for feat in features:
            fid = feat.get("id")
            if fid is not None and str(fid) == target:
                return feat
        return None

    def get_etag(self, scope: ScopeT, collection_id: str) -> str | None:
        """Return an ETag value for conditional requests, or ``None``.

        The string returned here is wrapped in double quotes by the
        view layer and sent as the ``ETag`` header. ``None`` disables
        conditional handling for this collection.
        """
        return None

    def get_cache_control(self, scope: ScopeT, collection_id: str) -> str:
        """Return the ``Cache-Control`` header value for *collection_id*.

        Default returns the service-wide :attr:`cache_control`. Project
        services override this to ship a shorter TTL when the SHA was
        resolved via a ``use_latest`` view: the URL stops being valid
        as soon as a new commit lands, so a 24-hour Cache-Control would
        let the CDN cache a 404 across deploys.
        """
        return self.cache_control


# ---------------------------------------------------------------------------
# Generic OGC view base classes (consume an OGCFeatureService)
# ---------------------------------------------------------------------------


class _OGCFeatureServiceView(GenericAPIView, SDBAPIViewMixin):  # type: ignore[type-arg]
    """Common base for OGC views — wires a service to a Django view.

    Subclasses set ``queryset``, ``lookup_field``, and ``service_class``;
    everything else (auth, pagination, headers) is handled by the
    generic view classes below.
    """

    schema = None
    permission_classes = [permissions.AllowAny]
    service_class: ClassVar[type[OGCFeatureService[Any]]]

    @cached_property
    def service(self) -> OGCFeatureService[Any]:
        """Return a (per-view) instance of the bound service."""
        return self.service_class()


class BaseOGCLandingPageApiView(_OGCFeatureServiceView):
    """OGC API - Features landing page (§7.2).

    Returns ``self``, ``conformance``, and ``data`` links. The ``data``
    link points to the canonical ``<base>/collections`` URL — clients
    follow it to discover collections.
    """

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> NoWrapResponse:
        # Validate the token / lookup; raises Http404 if invalid.
        self.get_object()
        landing_path = request.path.rstrip("/")
        return NoWrapResponse(
            build_landing_page(
                request=request,
                title=self.service.service_title,
                description=self.service.service_description,
                collections_path=f"{landing_path}/collections",
            )
        )


class BaseOGCConformanceApiView(_OGCFeatureServiceView):
    """OGC API - Features conformance declaration (§7.4)."""

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> NoWrapResponse:
        self.get_object()
        return NoWrapResponse(build_conformance_declaration())


class BaseOGCCollectionsApiView(_OGCFeatureServiceView):
    """OGC API - Features ``/collections`` list (§7.13)."""

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> NoWrapResponse:
        scope = self.get_object()
        metas = self.service.list_collections(scope)
        collections_path = request.path.rstrip("/")
        collections = [
            build_collection_metadata(
                collection_id=meta.id,
                title=meta.title,
                description=meta.description,
                request=request,
                self_path=f"{collections_path}/{meta.id}",
                items_path=f"{collections_path}/{meta.id}/items",
                bbox=meta.bbox,
            )
            for meta in metas
        ]
        return NoWrapResponse(
            build_collections_response(
                request=request,
                collections=collections,
            )
        )


class BaseOGCCollectionApiView(_OGCFeatureServiceView):
    """OGC API - Features single-collection metadata (§7.14)."""

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> NoWrapResponse:
        scope = self.get_object()
        collection_id: str = kwargs["collection_id"]
        meta = self.service.get_collection(scope, collection_id)
        if meta is None:
            raise Http404(f"Collection '{collection_id}' not found.")
        self_path = request.path.rstrip("/")
        return NoWrapResponse(
            build_collection_metadata(
                collection_id=meta.id,
                title=meta.title,
                description=meta.description,
                request=request,
                self_path=self_path,
                items_path=f"{self_path}/items",
                bbox=meta.bbox,
            )
        )


class BaseOGCCollectionItemsApiView(_OGCFeatureServiceView):
    """OGC API - Features ``/items`` endpoint (§7.15-7.16).

    Builds the response envelope per request via
    :func:`build_items_envelope` so that ``timeStamp`` is fresh and
    ``self`` reflects the actual request URL. Conditional requests
    (``If-None-Match``) short-circuit to 304 when the service supplies
    a stable ETag.
    """

    renderer_classes = [GeoJSONRenderer, LegacyGeoJSONRenderer, JSONRenderer]

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> StreamingHttpResponse | HttpResponseNotModified:
        scope = self.get_object()
        collection_id: str = kwargs["collection_id"]

        meta = self.service.get_collection(scope, collection_id)
        if meta is None:
            raise Http404(f"Collection '{collection_id}' not found.")

        # Parse OGC core query parameters; raises 400 on malformed input.
        query = parse_ogc_query(request)

        # Conditional request handling — only for the default item
        # representation. Filtered/paged requests are different
        # representations, so a collection-level ETag is not enough to
        # safely short-circuit them to 304.
        etag_value = self.service.get_etag(scope, collection_id)
        etag_header = f'"{etag_value}"' if etag_value else None
        cache_control = self.service.get_cache_control(scope, collection_id)
        if (
            etag_header
            and not request.query_params
            and request.headers.get("if-none-match") == etag_header
        ):
            response_nm = HttpResponseNotModified()
            response_nm["ETag"] = etag_header
            response_nm["Cache-Control"] = cache_control
            return response_nm

        features = self.service.get_features(scope, collection_id)
        sliced, number_matched = apply_ogc_query(features, query)

        payload = build_items_envelope(
            features=sliced,
            request=request,
            number_matched=number_matched,
            query=query,
        )
        content = orjson.dumps(payload)

        response = StreamingHttpResponse(
            streaming_content=[content],
            content_type="application/geo+json",
        )
        if etag_header:
            response["ETag"] = etag_header
        response["Cache-Control"] = cache_control
        response["Content-Disposition"] = "inline"
        return response


class BaseOGCSingleFeatureApiView(_OGCFeatureServiceView):
    """OGC API - Features single-feature endpoint (§7.17).

    Implements the OGC Core normative requirement (Req 31-33) of GET
    support at ``/collections/{collectionId}/items/{featureId}``.
    Returns 404 if either the collection or the feature is unknown.
    """

    renderer_classes = [GeoJSONRenderer, LegacyGeoJSONRenderer, JSONRenderer]

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> StreamingHttpResponse:
        scope = self.get_object()
        collection_id: str = kwargs["collection_id"]
        feature_id: str = kwargs["feature_id"]

        meta = self.service.get_collection(scope, collection_id)
        if meta is None:
            raise Http404(f"Collection '{collection_id}' not found.")

        feature = self.service.get_feature(scope, collection_id, feature_id)
        if feature is None:
            raise Http404(f"Feature '{feature_id}' not found.")

        payload = build_single_feature_response(
            feature=feature,
            request=request,
        )
        content = orjson.dumps(payload)

        response = StreamingHttpResponse(
            streaming_content=[content],
            content_type="application/geo+json",
        )
        etag_value = self.service.get_etag(scope, collection_id)
        if etag_value:
            response["ETag"] = f'"{etag_value}"'
        response["Cache-Control"] = self.service.get_cache_control(scope, collection_id)
        response["Content-Disposition"] = "inline"
        return response


# ---------------------------------------------------------------------------
# OGC OpenAPI service-desc — single document shared by every family
# ---------------------------------------------------------------------------


class OGCOpenAPIView(GenericAPIView, SDBAPIViewMixin):  # type: ignore[type-arg]
    """Serves the focused OGC API definition advertised by every family.

    OGC API - Features 1.0 §7.2.4 (Req 2 ``/req/core/root-success``)
    requires every landing page to advertise a ``rel:service-desc``
    link. The repository's global ``/api/schema/`` endpoint excludes
    OGC routes (`schema = None`) and weighs in at ~684 kB; this view
    serves a focused ~10-30 kB OpenAPI 3.0 document covering only the
    OGC route surface.

    The document, its bytes, and its ETag are pre-computed once at
    import time (see :mod:`speleodb.gis.ogc_openapi`); every request
    serves the same bytes from memory. ``If-None-Match`` requests
    short-circuit to 304 so subsequent fetches across deploys do not
    redownload identical content.
    """

    schema = None
    permission_classes = [permissions.AllowAny]
    # No DB lookup is performed — see ``get_object`` override below.
    queryset = None
    # The view returns a ``StreamingHttpResponse`` directly; no DRF
    # rendering happens. We keep both renderers so DRF's content
    # negotiation accepts ``Accept: application/vnd.oai.openapi+json``,
    # ``Accept: application/json``, and ``Accept: */*`` without 406-ing
    # before ``get`` runs.
    renderer_classes = [OpenAPI30Renderer, JSONRenderer]

    # The view does not consult the queryset at all — no model is being
    # looked up. Override ``get_object`` to be a no-op so DRF doesn't
    # try to evaluate ``self.queryset``.
    def get_object(self) -> None:
        return None

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> StreamingHttpResponse | HttpResponseNotModified:
        if request.headers.get("if-none-match") == OGC_OPENAPI_ETAG:
            response_nm = HttpResponseNotModified()
            response_nm["ETag"] = OGC_OPENAPI_ETAG
            response_nm["Cache-Control"] = OGC_OPENAPI_CACHE_CONTROL
            return response_nm

        response = StreamingHttpResponse(
            streaming_content=[OGC_OPENAPI_BYTES],
            content_type=OGC_OPENAPI_CONTENT_TYPE,
        )
        response["ETag"] = OGC_OPENAPI_ETAG
        response["Cache-Control"] = OGC_OPENAPI_CACHE_CONTROL
        response["Content-Disposition"] = "inline"
        return response


# ---------------------------------------------------------------------------
# Legacy mixed-collection 410 Gone view (geometry-typed split migration)
# ---------------------------------------------------------------------------


# OGC project per-commit collections used to be mixed-geometry under
# ``<sha>``. They were split per geometry group (see
# ``speleodb/gis/ogc_helpers.py`` / ``GEOMETRY_GROUPS``) so each
# OGC collection becomes a single-geometry GIS layer (the universal
# QGIS / ArcGIS Pro expectation). Requests to the old ``<sha>`` form
# return ``410 Gone`` with a ``Link: rel="alternate"`` header pointing
# at the geometry-typed replacements so existing clients see an
# explicit migration signal instead of a silent empty layer.
#
# The view is family-agnostic: the replacement URLs are computed from
# the request path itself by inserting ``_<group>`` after the SHA, so
# the same view serves the project-view (``/view/<token>/...``) and
# user-token (``/user/<key>/...``) families. Landmark families are
# unaffected — their data is Point-only by construction and never went
# through the mixed-collection era.
# The body is what most GIS clients (QGIS / ArcGIS Pro) display to
# the human user when they hit a 410. It must therefore READ LIKE A
# USER MESSAGE, not a developer note: "what do I do now?" rather than
# "what HTTP semantic was violated?". The Link header carries the
# machine-readable migration target for clients that follow it.
_LEGACY_GONE_BODY: bytes = orjson.dumps(
    {
        "title": (
            "This layer has been replaced "
            "\u2014 please re-add it from your OGC connection"
        ),
        "status": status.HTTP_410_GONE,
        "detail": (
            "This SpeleoDB project layer used to combine point stations "
            "and line passages in a single OGC collection. To match how "
            "QGIS and ArcGIS Pro handle geometry types (one collection "
            "= one layer = one geometry type), each project is now "
            "exposed as up to two separate collections: "
            "'<commit-sha>_points' for stations and "
            "'<commit-sha>_lines' for passages. "
            "Action required: in your GIS client, REMOVE this layer "
            "and re-add it from the same OGC server connection \u2014 "
            "the collections list now shows the new '_points' and "
            "'_lines' layers in its place. The exact replacement URLs "
            "for this specific layer are in the response 'Link' "
            'header (rel="alternate"). See '
            "docs/map-viewer/ogc-url-and-geometry-contract.md for the "
            "full migration guide."
        ),
        "type": "https://docs.ogc.org/is/17-069r4/17-069r4.html",
    }
)

# Splits ``<base>/collections/<sha>[<rest>]`` so the legacy URL can be
# rewritten to ``<base>/collections/<sha>_<group>[<rest>]``. The regex
# is anchored to the ``/collections/<sha>`` segment that the URL
# converter already validated, so unexpected shapes (none observed in
# practice) yield an empty Link header rather than a malformed one.
_LEGACY_GONE_LEADING_SHA_RE: re.Pattern[str] = re.compile(
    r"/collections/(?P<sha>[0-9a-fA-F]{6,40})(?P<rest>(?:/items.*)?)$",
)


class OGCLegacyMixedCollectionGoneView(GenericAPIView, SDBAPIViewMixin):  # type: ignore[type-arg]
    """410 Gone response for the pre-split ``<sha>`` collection URL.

    Built as a small standalone view (not an ``OGCFeatureService``
    subclass) because:

    * it never reads from S3 or the DB beyond the URL-routing layer's
      regex enforcement (the ``<gitsha:>`` converter already validated
      the SHA shape);
    * it returns the same structured 410 body for every family with a
      ``Link`` header derived from the request URL — Cache-Control is
      one-line simple (``no-store``: clients should not cache a
      migration signal across deploys).
    """

    schema = None
    permission_classes = [permissions.AllowAny]
    queryset = None

    def get_object(self) -> None:
        # No DB lookup — the URL converter regex is the only contract
        # the legacy form needs to satisfy and the response body does
        # not depend on the token.
        return None

    def _replacement_links(self, request: Request) -> list[str]:
        """Return RFC 5988 ``Link`` header entries for *request*.

        Builds one ``rel=alternate`` link per geometry group. Order
        matches ``GEOMETRY_GROUPS_ORDERED`` so logs and snapshots
        round-trip stably.
        """
        full_url = absolute_url(request)
        match = _LEGACY_GONE_LEADING_SHA_RE.search(full_url)
        if match is None:
            # The URL converter guaranteed the shape; defensive only.
            return []
        sha = match.group("sha").lower()
        rest = match.group("rest") or ""
        prefix = full_url[: match.start()]
        out: list[str] = []
        for group in GEOMETRY_GROUPS_ORDERED:
            href = f"{prefix}/collections/{sha}_{group}{rest}"
            out.append(f'<{href}>; rel="alternate"; type="application/geo+json"')
        return out

    def _gone_response(self, request: Request) -> HttpResponse:
        response = HttpResponse(
            content=_LEGACY_GONE_BODY,
            content_type="application/json",
            status=status.HTTP_410_GONE,
        )
        link_value = ", ".join(self._replacement_links(request))
        if link_value:
            response["Link"] = link_value
        # 410 is a permanent migration signal — clients should never
        # cache it across deploys (a future re-introduction of the
        # mixed form would otherwise stay invisible to any client
        # holding the cached response).
        response["Cache-Control"] = "no-store"
        return response

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        return self._gone_response(request)

    def head(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        return self._gone_response(request)
