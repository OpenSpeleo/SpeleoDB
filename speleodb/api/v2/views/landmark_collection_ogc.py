# -*- coding: utf-8 -*-

"""OGC API - Features views for SpeleoDB Landmark Collections.

Two endpoint families share the same generic view layer (defined in
:mod:`speleodb.api.v2.views.ogc_base`) via the ``OGCFeatureService``
abstraction:

* :class:`LandmarkSingleOGCService` — public ``gis_token``-scoped
  access to one specific :class:`LandmarkCollection`. Always exactly
  one OGC collection, conventionally named ``landmarks``.
* :class:`LandmarkUserOGCService` — application-token-scoped access to
  every active Landmark Collection the token's user is allowed to
  read; one OGC collection per UUID.

Both services hand back point-geometry features built by
:class:`LandmarkGeoJSONSerializer`, with conditional-request support via
an ETag derived from the collection state.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from uuid import UUID

from django.db.models import Count
from django.db.models import Max
from django.db.models import Min
from rest_framework.authtoken.models import Token

from speleodb.api.v2.landmark_access import accessible_landmark_collections_queryset
from speleodb.api.v2.serializers.landmark import LandmarkGeoJSONSerializer
from speleodb.api.v2.views.ogc_base import BaseOGCCollectionApiView
from speleodb.api.v2.views.ogc_base import BaseOGCCollectionItemsApiView
from speleodb.api.v2.views.ogc_base import BaseOGCCollectionsApiView
from speleodb.api.v2.views.ogc_base import BaseOGCConformanceApiView
from speleodb.api.v2.views.ogc_base import BaseOGCLandingPageApiView
from speleodb.api.v2.views.ogc_base import BaseOGCSingleFeatureApiView
from speleodb.api.v2.views.ogc_base import OGCCollectionMeta
from speleodb.api.v2.views.ogc_base import OGCFeatureService
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection

if TYPE_CHECKING:
    from datetime import datetime

# Stable id for the singular collection exposed by the gis_token-scoped
# (Landmark single) service. Persistence layer uses UUIDs but this
# token-scoped service has by definition exactly one collection, so a
# human-readable id is friendlier and matches the existing public
# contract.
#
# Disambiguation in client UIs: ArcGIS Pro and QGIS both display the
# OGC ``title`` field (not ``id``) in the layer table-of-contents.
# ``title`` is set to ``scope.name`` so multiple landmark tokens added
# to the same workspace render with distinct human labels even though
# all share the static collection id ``landmarks``. The static id
# keeps the public URL contract stable for users who bookmarked the
# ``/collections/landmarks/items`` form.
_LANDMARKS_COLLECTION_ID: str = "landmarks"

# Cache-Control for landmark items. Data is mutable so we use a short
# revalidating window; clients should rely on the strong ETag for fresh
# reads rather than the cache window.
_LANDMARK_CACHE_CONTROL: str = "public, max-age=60, must-revalidate"


# ---------------------------------------------------------------------------
# Shared ETag + serialization helpers (used by both landmark services)
# ---------------------------------------------------------------------------


def _landmark_collection_etag(collection: LandmarkCollection) -> str:
    """Return a strong ETag for *collection* derived from its state.

    The ETag captures everything that could change the items
    response: the collection's own ``modified_date``, the latest
    landmark ``modified_date``, and the landmark count. Any landmark
    add / update / delete invalidates the ETag.
    """
    agg = collection.landmarks.aggregate(
        latest=Max("modified_date"),
        landmark_count=Count("id"),
    )
    latest_landmark_modified: datetime | None = agg["latest"]
    landmark_count: int = agg["landmark_count"]
    latest_modified = (
        latest_landmark_modified.isoformat() if latest_landmark_modified else ""
    )
    payload = (
        f"{collection.id}:"
        f"{collection.modified_date.isoformat()}:"
        f"{latest_modified}:"
        f"{landmark_count}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _landmark_features(collection: LandmarkCollection) -> list[dict[str, Any]]:
    """Return the items list for *collection* using the shared serializer."""
    landmarks = collection.landmarks.select_related("collection").order_by("name")
    serializer = LandmarkGeoJSONSerializer(landmarks, many=True)
    return list(serializer.data)


def _landmark_feature(
    collection: LandmarkCollection, landmark_id: UUID
) -> dict[str, Any] | None:
    """Look up a single Landmark by id within *collection*; ``None`` if absent."""
    try:
        landmark = collection.landmarks.select_related("collection").get(
            id=landmark_id,
        )
    except Landmark.DoesNotExist:
        return None
    return LandmarkGeoJSONSerializer(landmark).data


def _parse_uuid(raw: str) -> UUID | None:
    """Return ``UUID(raw)`` or ``None`` if *raw* is not a valid UUID string."""
    try:
        return UUID(str(raw))
    except ValueError, TypeError:
        return None


def _landmark_collection_bbox(
    collection: LandmarkCollection,
) -> tuple[float, float, float, float] | None:
    """Compute the 2-D union bbox for *collection* via a single aggregate.

    Returns ``None`` for collections with no landmarks (the metadata
    falls back to the world-bbox fallback in
    :func:`speleodb.gis.ogc_helpers.build_collection_metadata`).
    """
    agg = collection.landmarks.aggregate(
        min_lon=Min("longitude"),
        max_lon=Max("longitude"),
        min_lat=Min("latitude"),
        max_lat=Max("latitude"),
    )
    if (
        agg["min_lon"] is None
        or agg["max_lon"] is None
        or agg["min_lat"] is None
        or agg["max_lat"] is None
    ):
        return None
    return (
        float(agg["min_lon"]),
        float(agg["min_lat"]),
        float(agg["max_lon"]),
        float(agg["max_lat"]),
    )


# ---------------------------------------------------------------------------
# OGCFeatureService — public single-collection (gis_token-scoped)
# ---------------------------------------------------------------------------


class LandmarkSingleOGCService(OGCFeatureService[LandmarkCollection]):
    """OGC feature service for a single ``LandmarkCollection``.

    The auth scope IS the single collection (resolved by
    ``gis_token`` lookup); the service exposes exactly one OGC
    collection named ``landmarks``.
    """

    service_title: ClassVar[str] = "SpeleoDB Landmark Collection"
    service_description: ClassVar[str] = (
        "OGC API - Features endpoint for Landmark Point data."
    )
    cache_control: ClassVar[str] = _LANDMARK_CACHE_CONTROL

    def list_collections(
        self,
        scope: LandmarkCollection,
    ) -> list[OGCCollectionMeta]:
        return [
            OGCCollectionMeta(
                id=_LANDMARKS_COLLECTION_ID,
                title=scope.name,
                description=scope.description or "",
                bbox=_landmark_collection_bbox(scope),
            ),
        ]

    def get_collection(
        self,
        scope: LandmarkCollection,
        collection_id: str,
    ) -> OGCCollectionMeta | None:
        if collection_id != _LANDMARKS_COLLECTION_ID:
            return None
        return OGCCollectionMeta(
            id=_LANDMARKS_COLLECTION_ID,
            title=scope.name,
            description=scope.description or "",
            bbox=_landmark_collection_bbox(scope),
        )

    def get_features(
        self,
        scope: LandmarkCollection,
        collection_id: str,
    ) -> list[dict[str, Any]]:
        # collection_id already validated by get_collection() in the
        # generic view; retain a defensive check so direct callers
        # cannot bypass the contract.
        if collection_id != _LANDMARKS_COLLECTION_ID:
            return []
        return _landmark_features(scope)

    def get_feature(
        self,
        scope: LandmarkCollection,
        collection_id: str,
        feature_id: str,
    ) -> dict[str, Any] | None:
        if collection_id != _LANDMARKS_COLLECTION_ID:
            return None
        landmark_id = _parse_uuid(feature_id)
        if landmark_id is None:
            return None
        return _landmark_feature(scope, landmark_id)

    def get_etag(
        self,
        scope: LandmarkCollection,
        collection_id: str,
    ) -> str | None:
        if collection_id != _LANDMARKS_COLLECTION_ID:
            return None
        return _landmark_collection_etag(scope)


# ---------------------------------------------------------------------------
# OGCFeatureService — user-token-scoped (multiple collections)
# ---------------------------------------------------------------------------


class LandmarkUserOGCService(OGCFeatureService[Token]):
    """OGC feature service for every active LandmarkCollection a user can read.

    The auth scope is a DRF ``Token``; the service yields one OGC
    collection per UUID the token's user has at least READ permission
    on. Inactive collections and inactive permissions are excluded.
    """

    service_title: ClassVar[str] = "SpeleoDB Landmark Collections"
    service_description: ClassVar[str] = (
        "OGC API - Features endpoint for all active Landmark Collections "
        "the token owner can read."
    )
    cache_control: ClassVar[str] = _LANDMARK_CACHE_CONTROL

    def __init__(self) -> None:
        self._resolved_collection_cache: dict[str, LandmarkCollection | None] = {}

    def _resolve_collection(
        self,
        scope: Token,
        collection_id: str,
    ) -> LandmarkCollection | None:
        """Resolve *collection_id* to an accessible LandmarkCollection."""
        if collection_id in self._resolved_collection_cache:
            return self._resolved_collection_cache[collection_id]

        uuid_id = _parse_uuid(collection_id)
        if uuid_id is None:
            self._resolved_collection_cache[collection_id] = None
            return None
        try:
            # OGC endpoints are read-only — never create the personal
            # collection on a GET (read-replica safety, cold-start cost).
            collection = accessible_landmark_collections_queryset(
                user=scope.user,
                ensure_personal=False,
            ).get(id=uuid_id)
        except LandmarkCollection.DoesNotExist:
            self._resolved_collection_cache[collection_id] = None
            return None
        self._resolved_collection_cache[collection_id] = collection
        return collection

    def list_collections(self, scope: Token) -> list[OGCCollectionMeta]:
        # Read-only path — see _resolve_collection. Per-collection bbox
        # is computed lazily in ``get_collection`` (one aggregate query
        # per /collections/{id} hit) rather than here, to keep the
        # /collections list O(1) instead of O(N) aggregate queries.
        return [
            OGCCollectionMeta(
                id=str(c.id),
                title=c.name,
                description=c.description or "",
            )
            for c in accessible_landmark_collections_queryset(
                user=scope.user,
                ensure_personal=False,
            )
        ]

    def get_collection(
        self,
        scope: Token,
        collection_id: str,
    ) -> OGCCollectionMeta | None:
        collection = self._resolve_collection(scope, collection_id)
        if collection is None:
            return None
        return OGCCollectionMeta(
            id=str(collection.id),
            title=collection.name,
            description=collection.description or "",
            bbox=_landmark_collection_bbox(collection),
        )

    def get_features(
        self,
        scope: Token,
        collection_id: str,
    ) -> list[dict[str, Any]]:
        collection = self._resolve_collection(scope, collection_id)
        if collection is None:
            return []
        return _landmark_features(collection)

    def get_feature(
        self,
        scope: Token,
        collection_id: str,
        feature_id: str,
    ) -> dict[str, Any] | None:
        collection = self._resolve_collection(scope, collection_id)
        if collection is None:
            return None
        landmark_id = _parse_uuid(feature_id)
        if landmark_id is None:
            return None
        return _landmark_feature(collection, landmark_id)

    def get_etag(self, scope: Token, collection_id: str) -> str | None:
        collection = self._resolve_collection(scope, collection_id)
        if collection is None:
            return None
        return _landmark_collection_etag(collection)


# ---------------------------------------------------------------------------
# View bindings (each one is a 3-line wrapper)
# ---------------------------------------------------------------------------

# Single-collection (public gis_token) endpoints.


class LandmarkCollectionOGCLandingPageApiView(BaseOGCLandingPageApiView):
    """OGC landing page for a public Landmark Collection token."""

    queryset = LandmarkCollection.objects.filter(is_active=True)
    lookup_field = "gis_token"
    service_class = LandmarkSingleOGCService


class LandmarkCollectionOGCConformanceApiView(BaseOGCConformanceApiView):
    """OGC conformance declaration for a public Landmark Collection token."""

    queryset = LandmarkCollection.objects.filter(is_active=True)
    lookup_field = "gis_token"
    service_class = LandmarkSingleOGCService


class LandmarkCollectionOGCCollectionsApiView(BaseOGCCollectionsApiView):
    """OGC ``/collections`` for a public Landmark Collection token."""

    queryset = LandmarkCollection.objects.filter(is_active=True)
    lookup_field = "gis_token"
    service_class = LandmarkSingleOGCService


class LandmarkCollectionOGCCollectionApiView(BaseOGCCollectionApiView):
    """OGC single-collection metadata for Landmark Points."""

    queryset = LandmarkCollection.objects.filter(is_active=True)
    lookup_field = "gis_token"
    service_class = LandmarkSingleOGCService


class LandmarkCollectionOGCCollectionItemsApiView(BaseOGCCollectionItemsApiView):
    """OGC ``/items`` endpoint for a public Landmark Collection."""

    queryset = LandmarkCollection.objects.filter(is_active=True)
    lookup_field = "gis_token"
    service_class = LandmarkSingleOGCService


class LandmarkCollectionOGCSingleFeatureApiView(BaseOGCSingleFeatureApiView):
    """OGC ``/items/{featureId}`` endpoint for a public Landmark Collection."""

    queryset = LandmarkCollection.objects.filter(is_active=True)
    lookup_field = "gis_token"
    service_class = LandmarkSingleOGCService


# User-token (application token) endpoints.


class LandmarkCollectionUserOGCLandingPageApiView(BaseOGCLandingPageApiView):
    """OGC landing page for user-token Landmark Collections."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"
    service_class = LandmarkUserOGCService


class LandmarkCollectionUserOGCConformanceApiView(BaseOGCConformanceApiView):
    """OGC conformance declaration for user-token Landmark Collections."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"
    service_class = LandmarkUserOGCService


class LandmarkCollectionUserOGCCollectionsApiView(BaseOGCCollectionsApiView):
    """OGC ``/collections`` for every user-readable Landmark Collection."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"
    service_class = LandmarkUserOGCService


class LandmarkCollectionUserOGCCollectionApiView(BaseOGCCollectionApiView):
    """OGC metadata for one readable user-token Landmark Collection."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"
    service_class = LandmarkUserOGCService


class LandmarkCollectionUserOGCCollectionItemsApiView(BaseOGCCollectionItemsApiView):
    """OGC ``/items`` for one user-token Landmark Collection."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"
    service_class = LandmarkUserOGCService


class LandmarkCollectionUserOGCSingleFeatureApiView(BaseOGCSingleFeatureApiView):
    """OGC ``/items/{featureId}`` for one user-token Landmark Collection."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"
    service_class = LandmarkUserOGCService
