# -*- coding: utf-8 -*-

"""OGC API - Features views scoped to a **GIS View** (``gis_token``).

Each project commit in the view is one OGC collection. The OGC contract
(landing/conformance/collections/collection/items/single-feature) is
implemented in :mod:`speleodb.api.v2.views.ogc_base`; this module only
provides:

* the non-OGC private and public viewer endpoints for the SpeleoDB map
  viewer (``GISViewDataApiView``, ``PublicGISViewGeoJSONApiView``);
* :class:`ProjectViewOGCService` — the ``OGCFeatureService`` adapter for
  GIS-View-scoped projects;
* 3-line view bindings that wire the service to the URL configuration.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

import orjson
import sentry_sdk
from django.core.cache import cache
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v2.permissions import GISViewOwnershipPermission
from speleodb.api.v2.serializers.gis_view import GISViewDataSerializer
from speleodb.api.v2.serializers.gis_view import PublicGISViewSerializer
from speleodb.api.v2.views.ogc_base import BaseOGCCollectionApiView
from speleodb.api.v2.views.ogc_base import BaseOGCCollectionItemsApiView
from speleodb.api.v2.views.ogc_base import BaseOGCCollectionsApiView
from speleodb.api.v2.views.ogc_base import BaseOGCConformanceApiView
from speleodb.api.v2.views.ogc_base import BaseOGCLandingPageApiView
from speleodb.api.v2.views.ogc_base import BaseOGCSingleFeatureApiView
from speleodb.api.v2.views.ogc_base import OGCCollectionMeta
from speleodb.api.v2.views.ogc_base import OGCFeatureService
from speleodb.gis.models import GISProjectView
from speleodb.gis.models import GISView
from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.ogc_helpers import GEOMETRY_GROUPS_ORDERED
from speleodb.gis.ogc_helpers import classify_geometry
from speleodb.gis.ogc_helpers import collection_bbox_2d_for_group
from speleodb.gis.ogc_helpers import filter_features_by_geometry_group
from speleodb.gis.ogc_helpers import geometry_groups_present
from speleodb.gis.ogc_helpers import normalize_features
from speleodb.gis.ogc_helpers import parse_typed_collection_id
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response


logger = logging.getLogger(__name__)


# Cache timeout for the per-commit normalized features list. Content is
# tied to a git commit SHA and therefore immutable, so 24 h is
# conservative — the data can never change for a given key.
_GEOJSON_CACHE_TIMEOUT: int = 60 * 60 * 24
_GEOJSON_CACHE_LOCK_TIMEOUT: int = 60
_GEOJSON_CACHE_LOCK_RETRIES: int = 50
_GEOJSON_CACHE_LOCK_WAIT_SECONDS: float = 0.1

# Hard upper bound on the orjson-serialised feature list we are willing
# to cache, in bytes. Memcached's default ``-I`` flag is 1 MiB; Redis is
# more permissive but we still don't want to push 50 MB Python objects
# through the cache layer for a 50 000-feature cave system. Above this
# threshold the request is served by reading directly from S3 and the
# cache is skipped — slow but correct, never broken.
_GEOJSON_CACHE_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MiB

# Min/max bounds for the GIS-View-data ``expires_in`` query parameter.
_EXPIRES_IN_DEFAULT: int = 3600
_EXPIRES_IN_MIN: int = 60
_EXPIRES_IN_MAX: int = 86_400

# Cache-Control for items on a ``use_latest=True`` view. The latest SHA
# changes whenever a new commit lands; if we shipped the default 24 h
# ``max-age`` the CDN would pin the now-stale 404 (or worse, a still-
# live 200 for an old commit) for the full window. 5 minutes plus a
# strong ETag keeps revalidation cheap while bounding the staleness
# horizon. Explicit-SHA collections are immutable so they keep the
# 24 h TTL (see ``cache_control`` on :class:`ProjectViewOGCService`).
_USE_LATEST_CACHE_CONTROL: str = "public, max-age=300, must-revalidate"


# ---------------------------------------------------------------------------
# Shared feature loader (cached by commit SHA — content is immutable)
# ---------------------------------------------------------------------------


def _read_normalized_features_from_storage(commit_sha: str) -> list[dict[str, Any]]:
    """Read, parse, and normalize the immutable GeoJSON for *commit_sha*."""
    try:
        project_geojson = ProjectGeoJSON.objects.select_related("commit").get(
            commit__id=commit_sha,
        )
    except ProjectGeoJSON.DoesNotExist:
        return []
    with project_geojson.file.open("rb") as f:
        raw_features = orjson.loads(f.read()).get("features", [])
    return normalize_features(raw_features, commit_sha=commit_sha)


def _build_feature_index(
    features: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build a ``{str(id): feature}`` lookup table from *features*.

    Used by :func:`_load_feature_by_id` to short-circuit the O(N) linear
    scan that would otherwise dominate ArcGIS Pro edit-tracking sessions
    (one ``/items/{featureId}`` per row, N rows = O(N^2)).
    """
    index: dict[str, dict[str, Any]] = {}
    for feat in features:
        fid = feat.get("id")
        if fid is not None:
            index[str(fid)] = feat
    return index


def _cache_features_if_under_limit(
    cache_key: str,
    features: list[dict[str, Any]],
) -> None:
    """Cache *features* under *cache_key* iff the serialised payload fits.

    Memcached rejects values above its ``-I`` cap (default 1 MiB), Redis
    silently accepts much bigger values but pinning a 50 MB Python
    object in a shared cache is wasteful regardless. Skipping cache.set
    above :data:`_GEOJSON_CACHE_MAX_BYTES` degrades the next request to
    a fresh S3 read — slow but correct, and the request still serves a
    200.
    """
    try:
        size = len(orjson.dumps(features))
    except TypeError, ValueError:
        # Anything we can't serialise we definitely can't safely cache.
        return
    if size > _GEOJSON_CACHE_MAX_BYTES:
        logger.warning(
            "OGC features payload for %s is %d bytes (>%d); skipping cache.set",
            cache_key,
            size,
            _GEOJSON_CACHE_MAX_BYTES,
        )
        return
    cache.set(cache_key, features, timeout=_GEOJSON_CACHE_TIMEOUT)


def _cache_index_if_features_cached(
    features_cache_key: str,
    features: list[dict[str, Any]],
) -> None:
    """Cache the ``{id: feature}`` index iff the features list itself fits.

    The index has the same upper bound as the features list (one ref per
    feature), so the size check on ``features`` is a sufficient proxy.
    Skipping the index cache when the features list doesn't fit keeps
    the two caches in lockstep — never have an index without its
    features.
    """
    try:
        size = len(orjson.dumps(features))
    except TypeError, ValueError:
        return
    if size > _GEOJSON_CACHE_MAX_BYTES:
        return
    suffix = features_cache_key.removeprefix("ogc_geojson_features_")
    index_key = f"ogc_geojson_features_index_{suffix}"
    cache.set(
        index_key,
        _build_feature_index(features),
        timeout=_GEOJSON_CACHE_TIMEOUT,
    )


def _load_normalized_features(commit_sha: str) -> list[dict[str, Any]]:
    """Load + normalize + cache the feature list for *commit_sha*.

    Cache key uses the ``ogc_geojson_features_`` prefix to retire the
    previous unfiltered/uncoded ``ogc_geojson_`` key (the old key
    orphans-out within its 24 h TTL). The cached value is a Python list
    of feature dicts, not bytes — the OGC envelope is built per-request
    by :func:`speleodb.gis.ogc_helpers.build_items_envelope` so that
    ``timeStamp`` and the ``self`` link are always fresh (OGC Req 29).

    Payloads above :data:`_GEOJSON_CACHE_MAX_BYTES` are loaded from
    storage on every request (cache.set is skipped) so a project with
    an unusually large GeoJSON file does not blow up the cache backend.

    The companion ``{id: feature}`` index is filled in the same
    critical section (see :func:`_load_feature_by_id`).
    """
    cache_key = f"ogc_geojson_features_{commit_sha}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached  # type: ignore[no-any-return]

    lock_key = f"{cache_key}:lock"
    if cache.add(lock_key, "1", timeout=_GEOJSON_CACHE_LOCK_TIMEOUT):
        try:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached  # type: ignore[no-any-return]
            features = _read_normalized_features_from_storage(commit_sha)
            _cache_features_if_under_limit(cache_key, features)
            _cache_index_if_features_cached(cache_key, features)
            return features
        finally:
            cache.delete(lock_key)

    for _ in range(_GEOJSON_CACHE_LOCK_RETRIES):
        time.sleep(_GEOJSON_CACHE_LOCK_WAIT_SECONDS)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[no-any-return]

    # If the filling worker died, serve the request rather than hanging.
    features = _read_normalized_features_from_storage(commit_sha)
    _cache_features_if_under_limit(cache_key, features)
    _cache_index_if_features_cached(cache_key, features)
    return features


def _load_collection_bbox(
    commit_sha: str,
    group: str,
) -> tuple[float, float, float, float] | None:
    """Return the cached 2-D bbox for *commit_sha* features in *group*.

    Computed lazily on first access from the cached features list and
    cached separately so subsequent /collections/<id> requests serve a
    real spatial extent for the geometry-typed layer (Points-only or
    Lines-only) without re-walking the features. Returns ``None`` for
    empty groups or for SHAs whose payload was too big to cache (in
    which case the collection metadata falls back to the world bbox —
    acceptable, never wrong).

    Cache key shape: ``ogc_geojson_bbox_{sha}_{group}``. The previous
    un-grouped key (``ogc_geojson_bbox_{sha}``) is no longer queried
    after the geometry split and will expire naturally on its own
    24 h TTL.
    """
    bbox_key = f"ogc_geojson_bbox_{commit_sha}_{group}"
    cached = cache.get(bbox_key)
    if cached is not None:
        # Cache stores ``("none",)`` for "we tried, no bbox" so we don't
        # re-walk on every call.
        if cached == ("none",):
            return None
        return cached  # type: ignore[no-any-return]

    features = _load_normalized_features(commit_sha)
    bbox = collection_bbox_2d_for_group(features, group)
    if bbox is None:
        cache.set(bbox_key, ("none",), timeout=_GEOJSON_CACHE_TIMEOUT)
        return None
    cache.set(bbox_key, bbox, timeout=_GEOJSON_CACHE_TIMEOUT)
    return bbox


def _load_geometry_groups_present(commit_sha: str) -> frozenset[str]:
    """Return the cached set of geometry groups present at *commit_sha*.

    Drives ``ProjectViewOGCService.list_collections`` so the
    ``/collections`` listing only enumerates groups that actually have
    features (no empty layers in QGIS / ArcGIS Pro). Cached separately
    from the features list so the discovery path stays a single
    ``cache.get`` per project commit on the warm path.

    A SHA whose features list does not load (DoesNotExist or not yet
    indexed) reports an empty set; the caller treats that as "no
    collections for this SHA", which surfaces as a 404 from the
    routing layer — never as a phantom layer in the client UI.
    """
    groups_key = f"ogc_geojson_groups_present_{commit_sha}"
    cached = cache.get(groups_key)
    if cached is not None:
        return frozenset(cached)

    features = _load_normalized_features(commit_sha)
    groups = frozenset(geometry_groups_present(features))
    # Persist as a tuple for cache-backend compatibility (memcached
    # rejects sets); the readback above re-wraps in a frozenset so
    # callers always see an immutable value.
    cache.set(groups_key, tuple(sorted(groups)), timeout=_GEOJSON_CACHE_TIMEOUT)
    return groups


def _load_feature_by_id(
    commit_sha: str,
    feature_id: str,
    group: str,
) -> dict[str, Any] | None:
    """Look up a single feature by id within *group* with O(1) cache hit.

    Tries the cached ``{id: feature}`` index first; on miss, falls back
    to loading the full features list (which also rebuilds and caches
    the index). Returns ``None`` if no feature has the requested id
    OR the matching feature's geometry does not belong to *group*
    (i.e. the URL collection_id and the actual feature geometry
    disagree — typically a stale client URL after the geometry-typed
    split).

    The features index is shared across all groups at the same SHA
    (one feature has one id, and that id is unique across the entire
    project); ``group`` is used to filter the lookup result, not the
    cached object. This keeps the ArcGIS Pro 3.6 edit-tracking hot
    path (one ``/items/{featureId}`` per modified row) at a single
    cache GET plus a dict access regardless of how many groups exist.
    """
    index_key = f"ogc_geojson_features_index_{commit_sha}"
    target = str(feature_id)

    def _filter_to_group(feat: dict[str, Any] | None) -> dict[str, Any] | None:
        if feat is None or classify_geometry(feat.get("geometry")) != group:
            return None
        return feat

    cached_index = cache.get(index_key)
    if cached_index is not None:
        return _filter_to_group(cached_index.get(target))

    # Index missing — touch the features path which (re)builds it.
    features = _load_normalized_features(commit_sha)
    cached_index = cache.get(index_key)
    if cached_index is not None:
        return _filter_to_group(cached_index.get(target))

    # Last-resort linear scan: only happens when the payload is too
    # large to cache; both index and list are uncached here.
    for feat in features:
        fid = feat.get("id")
        if fid is not None and str(fid) == target:
            return _filter_to_group(feat)
    return None


# ---------------------------------------------------------------------------
# OGCFeatureService for GIS-View-scoped projects
# ---------------------------------------------------------------------------


def _project_authorized_for_view(
    scope: GISView,
    project_geojson: ProjectGeoJSON,
    commit_sha: str,
) -> bool:
    """Return ``True`` iff *commit_sha* is reachable through *scope*.

    A commit is reachable when either:

    * a ``GISProjectView`` row pins exactly that commit on the view
      (explicit-SHA membership), or
    * a ``GISProjectView`` row marks the project as ``use_latest=True``
      AND the requested commit IS the latest commit for that project.

    Extracted from the previous monolithic ``get_collection`` so the
    geometry-typed split (which calls this once per ``<sha>_<group>``
    request) does not duplicate authorization logic per group.
    """
    project_rows = GISProjectView.objects.filter(
        gis_view=scope,
        project=project_geojson.project,
    )
    if project_rows.filter(commit_sha=commit_sha).exists():
        return True
    latest_commit_id = (
        ProjectGeoJSON.objects.filter(project=project_geojson.project)
        .order_by("-commit__authored_date")
        .values_list("commit_id", flat=True)
        .first()
    )
    return (
        latest_commit_id == commit_sha and project_rows.filter(use_latest=True).exists()
    )


def _build_typed_collection_meta(
    *,
    project_name: str,
    commit_sha: str,
    group: str,
    bbox: tuple[float, float, float, float] | None,
) -> OGCCollectionMeta:
    """Build the ``OGCCollectionMeta`` for ``<sha>_<group>``.

    Centralised so the title/description shape is identical between
    ``list_collections`` and ``get_collection`` (snapshot tests catch
    drift between the two paths).
    """
    return OGCCollectionMeta(
        id=f"{commit_sha}_{group}",
        title=f"{project_name} ({group})",
        description=f"Commit: {commit_sha} ({group} only)",
        bbox=bbox,
    )


class ProjectViewOGCService(OGCFeatureService[GISView]):
    """OGC feature service for projects in a single ``GISView``.

    Each project commit becomes **up to two** OGC collections, one per
    geometry group actually present in the GeoJSON: ``<sha>_points``
    (Point + MultiPoint) and ``<sha>_lines`` (LineString +
    MultiLineString). Polygons are not part of this product (cave-
    survey data does not produce them) — see
    ``speleodb/gis/ogc_helpers.py`` / ``GEOMETRY_GROUPS``.

    A geometry-typed collection is only listed in ``/collections`` when
    that group is present in the underlying GeoJSON; ``use_latest``
    views auto-resolve to the latest project commit at request time.
    """

    service_title: ClassVar[str] = "SpeleoDB GIS View"
    service_description: ClassVar[str] = (
        "OGC API - Features endpoint for a SpeleoDB GIS view. "
        "Each project commit appears as one collection per geometry "
        "type actually present (`<sha>_points`, `<sha>_lines`)."
    )
    cache_control: ClassVar[str] = "public, max-age=86400"

    def list_collections(self, scope: GISView) -> list[OGCCollectionMeta]:
        # The /collections list deliberately omits the per-collection
        # bbox: computing it cold would issue one DB+S3 read per
        # collection (and now per geometry group), turning the
        # discovery handshake into N*K storage reads for a project
        # with N commits and K groups. ArcGIS Pro and QGIS both fetch
        # /collections/{id} before adding a layer, which is where
        # ``_load_collection_bbox`` actually fires. Geometry-group
        # presence is resolved here so we do not enumerate empty
        # layers: warm path is one groups-cache GET per SHA; cold path
        # loads the normalized feature list once per SHA to compute it.
        out: list[OGCCollectionMeta] = []
        for d in scope.get_view_geojson_data():
            commit_sha: str = d["project_geojson"].commit_sha
            project_name: str = d["project_name"]
            present = _load_geometry_groups_present(commit_sha)
            for group in GEOMETRY_GROUPS_ORDERED:
                if group not in present:
                    continue
                out.append(
                    _build_typed_collection_meta(
                        project_name=project_name,
                        commit_sha=commit_sha,
                        group=group,
                        bbox=None,
                    )
                )
        return out

    def get_collection(
        self,
        scope: GISView,
        collection_id: str,
    ) -> OGCCollectionMeta | None:
        # SHA case invariant: ``ProjectCommit.id`` is stored lowercase
        # (git convention) and ``GISProjectView.commit_sha`` is forced
        # lowercase on save. ``parse_typed_collection_id`` lower-cases
        # the SHA half so the ORM lookup is canonical regardless of
        # how the user-typed URL was cased.
        parsed = parse_typed_collection_id(collection_id)
        if parsed is None:
            return None
        sha, group = parsed

        try:
            project_geojson = ProjectGeoJSON.objects.select_related(
                "project",
                "commit",
            ).get(commit__id=sha)
        except ProjectGeoJSON.DoesNotExist:
            return None
        if not _project_authorized_for_view(scope, project_geojson, sha):
            return None
        if group not in _load_geometry_groups_present(sha):
            # SHA exists and is reachable through the view, but this
            # geometry group has no features at this commit — surface
            # as 404 so QGIS / ArcGIS Pro do not add an empty layer.
            return None
        return _build_typed_collection_meta(
            project_name=project_geojson.project.name,
            commit_sha=sha,
            group=group,
            bbox=_load_collection_bbox(sha, group),
        )

    def get_features(
        self,
        scope: GISView,
        collection_id: str,
    ) -> list[dict[str, Any]]:
        # Authorization is the responsibility of get_collection() (the
        # generic view always calls it first). Here we just fetch the
        # commit-keyed cache and filter by geometry group — content
        # is invariant by commit SHA so the cache key is not scope-
        # sensitive.
        parsed = parse_typed_collection_id(collection_id)
        if parsed is None:
            return []
        sha, group = parsed
        return filter_features_by_geometry_group(
            _load_normalized_features(sha),
            group,
        )

    def get_feature(
        self,
        scope: GISView,
        collection_id: str,
        feature_id: str,
    ) -> dict[str, Any] | None:
        # O(1) lookup via the cached index, then a constant-time
        # geometry-group filter so a cross-group ``/items/{featureId}``
        # URL (typically a stale client) returns 404 instead of an
        # incoherent feature.
        parsed = parse_typed_collection_id(collection_id)
        if parsed is None:
            return None
        sha, group = parsed
        return _load_feature_by_id(sha, feature_id, group)

    def get_etag(self, scope: GISView, collection_id: str) -> str | None:
        # Project commits are immutable, so the SHA + group itself is
        # a perfect ETag (a deploy that changes the geometry-classifier
        # would change the group → ETag → revalidate). Returning
        # anything else would be wasteful.
        parsed = parse_typed_collection_id(collection_id)
        if parsed is None:
            return None
        sha, group = parsed
        return f"{sha}_{group}"

    def get_cache_control(self, scope: GISView, collection_id: str) -> str:
        """Use a 5-minute TTL when the SHA was resolved via ``use_latest``.

        Otherwise the default 24 h ``max-age`` would let a CDN serve a
        stale 404 (the URL stops being valid as soon as a newer commit
        lands and the latest moves) for up to 24 hours. Geometry
        groups inherit the same TTL from the underlying SHA — they
        share the same immutability story.
        """
        parsed = parse_typed_collection_id(collection_id)
        if parsed is None:
            return self.cache_control
        sha, _group = parsed
        is_use_latest = GISProjectView.objects.filter(
            gis_view=scope,
            project__geojsons__commit__id=sha,
            use_latest=True,
        ).exists()
        if is_use_latest:
            return _USE_LATEST_CACHE_CONTROL
        return self.cache_control


# ---------------------------------------------------------------------------
# Private (authenticated) view endpoint — not OGC
# ---------------------------------------------------------------------------


class GISViewDataApiView(GenericAPIView[GISView], SDBAPIViewMixin):
    """Private read-only endpoint to retrieve GISView data.

    Query params:
        - ``expires_in``: signed-URL expiration in seconds
          (default: 3600, min: 60, max: 86400).
    """

    queryset = GISView.objects.all()
    permission_classes = [GISViewOwnershipPermission]
    serializer_class = GISViewDataSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gis_view = self.get_object()

        try:
            expires_in = int(
                request.query_params.get("expires_in", _EXPIRES_IN_DEFAULT)
            )
            expires_in = min(
                max(expires_in, _EXPIRES_IN_MIN),
                _EXPIRES_IN_MAX,
            )
        except ValueError, TypeError:
            expires_in = _EXPIRES_IN_DEFAULT

        try:
            serializer = GISViewDataSerializer(
                gis_view,
                context={"expires_in": expires_in},
            )
            return SuccessResponse(serializer.data)

        except Exception as e:
            logger.exception(
                "Error generating GeoJSON URLs for view %s",
                gis_view.id,
            )
            sentry_sdk.capture_exception(e)
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
    service_class = ProjectViewOGCService


class OGCGISViewConformanceApiView(BaseOGCConformanceApiView):
    """OGC conformance declaration for a GIS view."""

    queryset = GISView.objects.all()
    lookup_field = "gis_token"
    service_class = ProjectViewOGCService


class OGCGISViewCollectionsApiView(BaseOGCCollectionsApiView):
    """OGC ``/collections`` list for a GIS view."""

    queryset = GISView.objects.all()
    lookup_field = "gis_token"
    service_class = ProjectViewOGCService


class OGCGISViewCollectionApiView(BaseOGCCollectionApiView):
    """OGC single-collection metadata for a GIS-View project."""

    queryset = GISView.objects.all()
    lookup_field = "gis_token"
    service_class = ProjectViewOGCService


class OGCGISViewCollectionItemsApiView(BaseOGCCollectionItemsApiView):
    """OGC ``/items`` endpoint for a GIS-View project."""

    queryset = GISView.objects.all()
    lookup_field = "gis_token"
    service_class = ProjectViewOGCService


class OGCGISViewSingleFeatureApiView(BaseOGCSingleFeatureApiView):
    """OGC ``/items/{featureId}`` endpoint for a GIS-View project."""

    queryset = GISView.objects.all()
    lookup_field = "gis_token"
    service_class = ProjectViewOGCService


# ---------------------------------------------------------------------------
# Frontend map viewer endpoint (not OGC)
# ---------------------------------------------------------------------------


class PublicGISViewGeoJSONApiView(GenericAPIView[GISView], SDBAPIViewMixin):
    """Public endpoint returning GeoJSON URLs for the frontend map viewer.

    Usage: Public SpeleoDB map viewer at /view/<gis_token>/.
    """

    queryset = GISView.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = PublicGISViewSerializer
    lookup_field = "gis_token"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gis_view = self.get_object()
        try:
            serializer = PublicGISViewSerializer(
                gis_view,
                context={"expires_in": _EXPIRES_IN_DEFAULT},
            )
            return SuccessResponse(serializer.data)
        except Exception as e:
            logger.exception(
                "Error generating public GeoJSON data for view %s",
                gis_view.id,
            )
            sentry_sdk.capture_exception(e)
            return ErrorResponse(
                {"error": "Failed to load map data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
