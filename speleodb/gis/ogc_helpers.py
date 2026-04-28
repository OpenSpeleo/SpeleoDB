# -*- coding: utf-8 -*-

"""Shared OGC API - Features helpers used by every OGC endpoint family.

This module is the SINGLE SOURCE of truth for OGC compliance. Every fix
(``rel:self`` link, ``numberMatched``/``numberReturned``/``timeStamp``,
``crs``, ``extent``, ``bbox`` filtering, ``limit``/``offset`` pagination,
feature-id lifting, ``datetime`` validation) is implemented here exactly
once and consumed by all four OGC families: project-view, project-user,
landmark-single, landmark-user.

OGC API Features 1.0 normative requirements honoured in this module:

* Req 27 ``/req/core/fc-links`` — items SHALL include ``rel: self``.
* Req 29 ``/req/core/fc-timeStamp`` — if ``timeStamp`` is present it SHALL
  be the response generation time; the envelope is therefore built per
  request and never cached.
* Req 31 ``/req/core/fc-numberReturned`` — ``numberReturned`` SHALL equal
  the number of features in the response.
* ``/req/geojson/content`` B — ``links`` are added as an extension
  property of the FeatureCollection.
* §7.16.2 spec example 12 — items envelope shape.

Every public function in this module is pure: it takes inputs, validates
them, and returns plain Python values. There are no Django ORM queries,
no S3/CloudFront calls, and no cache reads/writes here — those live in
the per-family ``OGCFeatureService`` implementations.
"""

from __future__ import annotations

import logging
import math
import re
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any
from typing import Final
from urllib.parse import quote
from urllib.parse import urlparse
from urllib.parse import urlunparse

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from rest_framework.exceptions import ParseError

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Sequence

    from rest_framework.request import Request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OGC URI constants
# ---------------------------------------------------------------------------
# CRS84 is the OGC name for "WGS 84 with longitude/latitude order" and is
# the default CRS for OGC API Features. CRS84h is the 3-D variant
# (lon, lat, ellipsoidal height). Cave-survey data carries Z = depth in
# metres, so we advertise CRS84h alongside CRS84 to keep ArcGIS Pro from
# silently stripping the third coordinate when it builds the layer schema.
CRS84_2D: str = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
CRS84_3D: str = "http://www.opengis.net/def/crs/OGC/0/CRS84h"

# World bbox is acceptable per the OGC spec when a precomputed
# per-collection bbox is unavailable; better than omitting ``extent``
# entirely.
WORLD_BBOX_2D: list[list[float]] = [[-180.0, -90.0, 180.0, 90.0]]

# Maximum number of features served in a single ``/items`` response.
# Requests asking for more are rejected at validation time.
# OGC leaves this implementation-defined; 10_000 keeps responses under
# ~5 MB for typical cave-survey payloads.
MAX_OGC_LIMIT: int = 10_000
DEFAULT_OGC_LIMIT: int = MAX_OGC_LIMIT

# Path of the service-desc endpoint. Shared here because landing-page
# links are built in this module, while the OpenAPI document imports
# conformance constants from here.
OGC_OPENAPI_PATH: Final[str] = "/api/v2/gis-ogc/openapi/"

# CRS84 coordinate ranges.
_LON_MIN: float = -180.0
_LON_MAX: float = 180.0
_LAT_MIN: float = -90.0
_LAT_MAX: float = 90.0

# Bbox parameter forms accepted by OGC.
_BBOX_2D_LEN: int = 4
_BBOX_3D_LEN: int = 6

# Minimum number of coordinate components in a valid GeoJSON position.
_COORD_MIN_DIM: int = 2

# When self_url is ``.../items/{featureId}`` and we split on ``/`` from
# the right with maxsplit=2, we expect exactly three parts.
_FEATURE_URL_PARTS: int = 3

# OGC API Features 1.0 conformance classes the service implements.
OGC_CONFORMANCE_CLASSES: list[str] = [
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30",
]


# ---------------------------------------------------------------------------
# OGCQuery — parsed and validated query parameters
# ---------------------------------------------------------------------------


class OGCQuery(BaseModel):
    """Parsed OGC API Features query parameters.

    All four families share this parser. ``bbox``, ``datetime``,
    ``limit`` and ``offset`` are the OGC core query parameters honoured
    here; everything else is silently ignored (the OGC spec explicitly
    allows server-defined extensions).

    The ``bbox`` field is constrained to either a 4-tuple
    (``min_lon, min_lat, max_lon, max_lat``) or a 6-tuple
    (``min_lon, min_lat, min_z, max_lon, max_lat, max_z``). Any other
    arity is rejected at construction time so internal callers cannot
    accidentally bypass :func:`_parse_bbox` and feed
    :func:`_bbox_intersects` an unpackable shape.
    """

    bbox: tuple[float, ...] | None = None
    datetime_value: str | None = Field(default=None, alias="datetime")
    limit: int = DEFAULT_OGC_LIMIT
    offset: int = 0
    limit_was_supplied: bool = False
    offset_was_supplied: bool = False

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("bbox")
    @classmethod
    def _validate_bbox_arity(
        cls, value: tuple[float, ...] | None
    ) -> tuple[float, ...] | None:
        if value is None:
            return None
        if len(value) not in (_BBOX_2D_LEN, _BBOX_3D_LEN):
            raise ValueError(f"bbox must be 4 or 6 floats; got {len(value)}")
        return value


# Accepts RFC 3339 instants. We only validate the format, not the
# semantic value (e.g. leap seconds), because cave data has no temporal
# extent — datetime is a pass-through filter.
_RFC3339_INSTANT_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


_OPEN_INTERVAL_END: str = ".."


def _parse_datetime_segment(value: str) -> bool:
    """Return ``True`` if *value* is a valid RFC 3339 datetime or ``..``."""
    if value == _OPEN_INTERVAL_END:
        return True
    return bool(_RFC3339_INSTANT_RE.match(value))


def _parse_datetime(raw: str) -> str:
    """Validate an OGC ``datetime`` query parameter (instant or interval).

    Per OGC §7.15.4 the datetime parameter accepts:

    * an instant — ``2018-04-03T14:52:23Z``
    * a closed interval — ``<start>/<end>``
    * an open-start interval — ``../<end>``
    * an open-end interval — ``<start>/..``

    Raises :class:`ParseError` (HTTP 400) on malformed input. Returns the
    input unchanged on success — cave-survey collections have no temporal
    geometry, so the parameter is a pass-through filter.
    """
    if "/" in raw:
        parts = raw.split("/", 1)
        if len(parts) != 2 or not all(_parse_datetime_segment(p) for p in parts):  # noqa: PLR2004
            raise ParseError(
                f"Invalid datetime interval '{raw}'. Expected RFC 3339 "
                "instants separated by '/' (or '..' for open ends)."
            )
        return raw
    if not _parse_datetime_segment(raw):
        raise ParseError(
            f"Invalid datetime '{raw}'. Expected an RFC 3339 instant such "
            "as '2018-04-03T14:52:23Z'."
        )
    return raw


def _parse_bbox(raw: str) -> tuple[float, ...]:
    """Validate an OGC ``bbox`` query parameter.

    Per OGC §7.15.3:

    * 4 numbers — ``min_lon, min_lat, max_lon, max_lat`` (CRS84 order).
    * 6 numbers — ``min_lon, min_lat, min_z, max_lon, max_lat, max_z``.

    Raises :class:`ParseError` (HTTP 400) on malformed input.
    """
    parts = raw.split(",")
    if len(parts) not in (_BBOX_2D_LEN, _BBOX_3D_LEN):
        raise ParseError(
            f"Invalid bbox '{raw}'. Expected 4 or 6 comma-separated numbers."
        )
    try:
        values = tuple(float(p) for p in parts)
    except ValueError as exc:
        raise ParseError(f"Invalid bbox '{raw}': {exc}") from exc

    # Reject NaN / Infinity — they always fail intersection checks but
    # also poison numpy/Sentry metrics when accidentally surfaced.
    if any(math.isnan(v) or math.isinf(v) for v in values):
        raise ParseError(f"Invalid bbox '{raw}': NaN/Infinity not allowed.")

    if len(values) == _BBOX_2D_LEN:
        min_x, min_y, max_x, max_y = values
        if min_y > max_y:
            raise ParseError(
                f"Invalid bbox '{raw}': min latitude must not exceed max latitude."
            )
    else:
        min_x, min_y, _, max_x, max_y, _ = values
        if min_y > max_y or values[2] > values[5]:
            raise ParseError(
                f"Invalid bbox '{raw}': min latitude/Z must not exceed max latitude/Z."
            )

    if not (_LON_MIN <= min_x <= _LON_MAX and _LON_MIN <= max_x <= _LON_MAX):
        raise ParseError(
            f"Invalid bbox '{raw}': longitude out of [{_LON_MIN}, {_LON_MAX}]."
        )
    if not (_LAT_MIN <= min_y <= _LAT_MAX and _LAT_MIN <= max_y <= _LAT_MAX):
        raise ParseError(
            f"Invalid bbox '{raw}': latitude out of [{_LAT_MIN}, {_LAT_MAX}]."
        )

    return values


def _parse_int(raw: str, *, name: str, min_value: int, max_value: int) -> int:
    """Parse a bounded non-negative integer query parameter or raise 400."""
    try:
        value = int(raw)
    except ValueError as exc:
        raise ParseError(f"Invalid {name} '{raw}': must be an integer.") from exc
    if value < min_value or value > max_value:
        raise ParseError(
            f"Invalid {name} '{raw}': must be between {min_value} and {max_value}."
        )
    return value


def parse_ogc_query(request: Request) -> OGCQuery:
    """Parse the OGC core query parameters from *request*.

    Returns an :class:`OGCQuery` instance with validated values. Raises
    :class:`ParseError` (HTTP 400) on any malformed parameter.

    Unknown query parameters are silently ignored — OGC §7.15 explicitly
    allows server-defined extensions.
    """
    bbox_raw = request.query_params.get("bbox")
    datetime_raw = request.query_params.get("datetime")
    limit_raw = request.query_params.get("limit")
    offset_raw = request.query_params.get("offset")

    bbox = _parse_bbox(bbox_raw) if bbox_raw else None
    datetime_value = _parse_datetime(datetime_raw) if datetime_raw else None
    limit = (
        _parse_int(limit_raw, name="limit", min_value=1, max_value=MAX_OGC_LIMIT)
        if limit_raw
        else DEFAULT_OGC_LIMIT
    )
    offset = (
        _parse_int(offset_raw, name="offset", min_value=0, max_value=10**9)
        if offset_raw
        else 0
    )

    return OGCQuery(
        bbox=bbox,
        datetime=datetime_value,
        limit=limit,
        offset=offset,
        limit_was_supplied=limit_raw is not None,
        offset_was_supplied=offset_raw is not None,
    )


# ---------------------------------------------------------------------------
# Feature normalization & bbox computation
# ---------------------------------------------------------------------------


def _flatten_coords(geometry: dict[str, Any]) -> list[Sequence[float]]:
    """Flatten any GeoJSON geometry into a list of coordinate sequences.

    Returns an empty list for null or unrecognized geometries; this lets
    bbox filtering drop such features without raising.
    """
    if not geometry:
        return []
    out: list[Sequence[float]] = []
    geom_type = geometry.get("type")
    # GeometryCollection has ``geometries``, not ``coordinates``; recurse.
    if geom_type == "GeometryCollection":
        geometries = geometry.get("geometries")
        if not isinstance(geometries, (list, tuple)):
            return []
        for sub in geometries:
            if isinstance(sub, dict):
                out.extend(_flatten_coords(sub))
        return out
    coords = geometry.get("coordinates")
    if coords is None:
        return []
    if geom_type == "Point":
        if isinstance(coords, (list, tuple)) and len(coords) >= _COORD_MIN_DIM:
            return [coords]
        return []
    if geom_type in ("LineString", "MultiPoint"):
        if not isinstance(coords, (list, tuple)):
            return []
        return [
            c
            for c in coords
            if isinstance(c, (list, tuple)) and len(c) >= _COORD_MIN_DIM
        ]
    if geom_type in ("Polygon", "MultiLineString"):
        if not isinstance(coords, (list, tuple)):
            return []
        for ring in coords:
            if isinstance(ring, (list, tuple)):
                out.extend(
                    c
                    for c in ring
                    if isinstance(c, (list, tuple)) and len(c) >= _COORD_MIN_DIM
                )
        return out
    if geom_type == "MultiPolygon":
        if not isinstance(coords, (list, tuple)):
            return []
        for poly in coords:
            if not isinstance(poly, (list, tuple)):
                continue
            for ring in poly:
                if isinstance(ring, (list, tuple)):
                    out.extend(
                        c
                        for c in ring
                        if isinstance(c, (list, tuple)) and len(c) >= _COORD_MIN_DIM
                    )
        return out
    return []


def feature_bbox_2d(
    feature: dict[str, Any],
) -> tuple[float, float, float, float] | None:
    """Compute the 2-D bounding box of a GeoJSON feature.

    Returns ``None`` if the feature has no geometry or if no valid
    coordinate pair could be extracted. Used as the input to
    :func:`apply_ogc_query` for ``bbox`` filtering.
    """
    if not isinstance(feature, dict):
        return None
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict):
        return None
    coords = _flatten_coords(geometry)
    if not coords:
        return None
    try:
        xs = [float(c[0]) for c in coords]
        ys = [float(c[1]) for c in coords]
    except ValueError, TypeError, IndexError:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def collection_bbox_2d(
    features: Iterable[dict[str, Any]],
) -> tuple[float, float, float, float] | None:
    """Compute the union 2-D bbox across every feature in *features*.

    Returns ``None`` if no feature has a usable geometry. Used to
    populate ``extent.spatial.bbox`` on collection metadata documents
    so ArcGIS Pro / QGIS can zoom-to-fit when adding the layer instead
    of defaulting to the whole-world fallback.
    """
    min_x = math.inf
    min_y = math.inf
    max_x = -math.inf
    max_y = -math.inf
    seen = False
    for feat in features:
        fbbox = feature_bbox_2d(feat)
        if fbbox is None:
            continue
        seen = True
        fx_min, fy_min, fx_max, fy_max = fbbox
        min_x = min(min_x, fx_min)
        min_y = min(min_y, fy_min)
        max_x = max(max_x, fx_max)
        max_y = max(max_y, fy_max)
    if not seen:
        return None
    return (min_x, min_y, max_x, max_y)


def _bbox_intersects(
    a: tuple[float, float, float, float],
    b: tuple[float, ...],
) -> bool:
    """Return ``True`` if 2-D bboxes *a* and *b* share at least one point."""
    if len(b) == _BBOX_2D_LEN:
        bx_min, by_min, bx_max, by_max = b
    else:
        bx_min, by_min, _, bx_max, by_max, _ = b
    ax_min, ay_min, ax_max, ay_max = a
    if bx_min <= bx_max:
        x_intersects = not (ax_min > bx_max or ax_max < bx_min)
    else:
        # OGC bboxes may cross the antimeridian, represented as
        # west_lon > east_lon in CRS84 longitude order.
        x_intersects = ax_max >= bx_min or ax_min <= bx_max
    y_intersects = not (ay_min > by_max or ay_max < by_min)
    return x_intersects and y_intersects


def _dedupe_feature_id(
    feature_id: Any,
    seen_ids: set[str],
    index: int,
) -> Any:
    """Return a deterministic unique feature id within one collection."""
    feature_id_key = str(feature_id)
    if feature_id_key not in seen_ids:
        seen_ids.add(feature_id_key)
        return feature_id

    suffix = 1
    candidate = f"{feature_id_key}:{index}"
    while candidate in seen_ids:
        suffix += 1
        candidate = f"{feature_id_key}:{index}:{suffix}"
    seen_ids.add(candidate)
    return candidate


def normalize_features(
    features: Iterable[dict[str, Any]],
    *,
    commit_sha: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize a list of GeoJSON features for OGC compliance.

    For each feature:

    * If a top-level ``id`` is already present, it is preserved.
    * Otherwise, ``properties.id`` is lifted to top-level ``id`` (RFC
      7946 §3.2 ``SHOULD``; ArcGIS Pro relies on it for edit-tracking
      row identity).
    * If neither is present and *commit_sha* is given, a deterministic
      synthetic id ``"{commit_sha}:{index}"`` is assigned. Determinism
      across requests is required so single-feature endpoints
      (``/items/{featureId}``) remain stable for immutable project
      files.
    * If neither is present and no *commit_sha* is supplied, the feature
      is passed through without an id (acceptable: GeoJSON §3.2 says
      ``id`` is OPTIONAL).

    The function is pure: it returns a new list of new dicts and does
    not mutate the inputs.
    """
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, feat in enumerate(features):
        if not isinstance(feat, dict):
            continue
        if "id" in feat and feat["id"] is not None:
            new_feat = dict(feat)
            new_feat["id"] = _dedupe_feature_id(new_feat["id"], seen_ids, index)
            out.append(new_feat)
            continue
        props = feat.get("properties")
        props_id = props.get("id") if isinstance(props, dict) else None
        if props_id is not None:
            new_feat = dict(feat)
            new_feat["id"] = _dedupe_feature_id(props_id, seen_ids, index)
            out.append(new_feat)
            continue
        if commit_sha is not None:
            new_feat = dict(feat)
            new_feat["id"] = _dedupe_feature_id(
                f"{commit_sha}:{index}",
                seen_ids,
                index,
            )
            out.append(new_feat)
            continue
        out.append(dict(feat))
    return out


# ---------------------------------------------------------------------------
# Geometry-typed collection split (1 OGC collection = 1 GIS layer = 1
# uniform geometry — the universal QGIS / ArcGIS Pro expectation)
# ---------------------------------------------------------------------------
#
# SpeleoDB cave-survey data carries Point and LineString geometries (with
# their Multi* variants). A single FeatureCollection mixing both fails
# to render in QGIS and ArcGIS Pro because both clients treat one OGC
# collection as one map layer, and a map layer can only hold one
# geometry type. The fix is per-geometry-type collections.
#
# Polygons are intentionally NOT in ``GEOMETRY_GROUPS``: cave-survey
# data does not produce them. ``classify_geometry`` returns ``None``
# for any geometry type that is not in a declared group, so a stray
# polygon gets dropped (and a warning logged via
# ``filter_features_by_geometry_group`` / ``geometry_groups_present``)
# rather than silently corrupting a layer. Adding a polygon group
# later is a one-line change here plus the matching regex in
# ``speleodb/utils/url_converters.py``.

#: Geometry-group → set of GeoJSON geometry-type names mapped to it.
#: Drives ``classify_geometry``, the URL converter shape, and the
#: per-collection bbox loader.
GEOMETRY_GROUPS: Final[dict[str, frozenset[str]]] = {
    "points": frozenset({"Point", "MultiPoint"}),
    "lines": frozenset({"LineString", "MultiLineString"}),
}

#: Stable iteration order for ``/collections`` listings — points first
#: then lines so the per-project layer panel in QGIS / ArcGIS Pro
#: presents stations above passages (the natural cave-survey reading
#: order).
GEOMETRY_GROUPS_ORDERED: Final[tuple[str, ...]] = ("points", "lines")


def classify_geometry(geometry: dict[str, Any] | None) -> str | None:
    """Return the geometry-group name for *geometry* or ``None``.

    ``None`` means the geometry is unknown to this product
    (e.g. ``Polygon``, ``MultiPolygon``, ``GeometryCollection``, or
    a malformed payload). Callers MUST drop such features rather than
    place them in a typed collection — pinning the "no polygons in
    this product" invariant at the routing/filter boundary.
    """
    if not isinstance(geometry, dict):
        return None
    geom_type = geometry.get("type")
    if not isinstance(geom_type, str):
        return None
    for group, members in GEOMETRY_GROUPS.items():
        if geom_type in members:
            return group
    return None


# ``<commit-sha>_<group>`` collection-id parser. Mirrored by the
# ``ogc_typed_id`` URL converter regex
# (``[0-9a-fA-F]{6,40}_(?:points|lines)``); kept here so the service
# layer can validate ids that arrive through paths the URL routing
# layer cannot enforce (cache keys, single-feature sub-resources
# resolved through ``str:`` converters, etc.).
_TYPED_COLLECTION_ID_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<sha>[0-9a-fA-F]{6,40})_(?P<group>"
    + "|".join(re.escape(g) for g in GEOMETRY_GROUPS)
    + r")$"
)


def parse_typed_collection_id(collection_id: str) -> tuple[str, str] | None:
    """Return ``(commit_sha_lower, geometry_group)`` or ``None``.

    Defensive parser for the geometry-typed collection-id contract.
    Returns ``None`` for the legacy mixed ``<sha>``-only form (which
    the routing layer maps to a 410 Gone view) and for any other
    unrecognised shape.
    """
    if not isinstance(collection_id, str):
        return None
    match = _TYPED_COLLECTION_ID_RE.match(collection_id)
    if match is None:
        return None
    return match.group("sha").lower(), match.group("group")


def filter_features_by_geometry_group(
    features: Iterable[dict[str, Any]],
    group: str,
) -> list[dict[str, Any]]:
    """Return the subset of *features* whose geometry belongs to *group*.

    Single-pass filter; non-dict features and features outside any
    declared group are silently dropped. Callers that need to surface
    "polygon was dropped" should use ``geometry_groups_present`` first
    (it logs a warning when an unknown group is observed).
    """
    if group not in GEOMETRY_GROUPS:
        return []
    out: list[dict[str, Any]] = []
    for feat in features:
        if not isinstance(feat, dict):
            continue
        if classify_geometry(feat.get("geometry")) == group:
            out.append(feat)
    return out


def geometry_groups_present(features: Iterable[dict[str, Any]]) -> set[str]:
    """Return the set of geometry groups actually present in *features*.

    Walks the features once. Any feature whose geometry classifies as
    ``None`` (e.g. a Polygon — not part of this product) is dropped
    from the count and a single structured warning is emitted per
    encountered unknown geometry type so a future polygon-producing
    pipeline change is loud, not silent.
    """
    present: set[str] = set()
    unknown_types_seen: set[str] = set()
    for feat in features:
        if not isinstance(feat, dict):
            continue
        geometry = feat.get("geometry")
        group = classify_geometry(geometry)
        if group is not None:
            present.add(group)
            continue
        # Unknown geometry: log once per type per call so a polygon-
        # producing regression is visible in logs without flooding.
        if isinstance(geometry, dict):
            geom_type = geometry.get("type")
            if isinstance(geom_type, str) and geom_type not in unknown_types_seen:
                unknown_types_seen.add(geom_type)
                logger.warning(
                    "OGC geometry split: dropping unsupported geometry "
                    "type %r (no GEOMETRY_GROUPS entry). Add a group "
                    "in speleodb/gis/ogc_helpers.py and the matching "
                    "URL-converter regex if this is intentional.",
                    geom_type,
                    extra={
                        "unsupported_geometry_type": geom_type,
                        "ogc_geometry_groups": tuple(GEOMETRY_GROUPS),
                    },
                )
    return present


def collection_bbox_2d_for_group(
    features: Iterable[dict[str, Any]],
    group: str,
) -> tuple[float, float, float, float] | None:
    """Return the union 2-D bbox of *features* belonging to *group*.

    Wraps :func:`collection_bbox_2d` after filtering by geometry group;
    callers use this to populate ``extent.spatial.bbox`` on a typed
    collection's metadata response so QGIS / ArcGIS Pro auto-zoom
    lands on the actual data envelope per geometry layer.
    """
    if group not in GEOMETRY_GROUPS:
        return None
    return collection_bbox_2d(filter_features_by_geometry_group(features, group))


# ---------------------------------------------------------------------------
# OGC core query application
# ---------------------------------------------------------------------------


def apply_ogc_query(
    features: list[dict[str, Any]],
    query: OGCQuery,
) -> tuple[list[dict[str, Any]], int]:
    """Apply *query* to *features* and return ``(sliced, numberMatched)``.

    Steps (in order):

    1. ``bbox`` — drop features whose 2-D bbox does not intersect.
       Features with null/invalid geometry are dropped when a bbox is
       supplied and kept otherwise (so a missing geometry never crashes
       a default ``/items`` request).
    2. ``datetime`` — pass-through (cave data has no temporal extent).
    3. ``offset`` and ``limit`` slicing.

    ``numberMatched`` is the count after bbox/datetime filtering but
    before offset/limit slicing — the OGC spec is explicit that this is
    the total number of features matching the query, not the number
    returned in a single page.
    """
    if query.bbox is None:
        matched = list(features)
    else:
        matched = []
        for feat in features:
            fbbox = feature_bbox_2d(feat)
            if fbbox is None:
                continue
            if _bbox_intersects(fbbox, query.bbox):
                matched.append(feat)

    # datetime: pass-through validation only — no filtering.

    number_matched = len(matched)

    start = query.offset
    sliced = matched[start : start + query.limit]
    return sliced, number_matched


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def absolute_url(request: Request, *, path: str | None = None) -> str:
    """Build an absolute URL from request scheme/host plus *path*.

    Uses ``request.path`` (NOT ``request.get_full_path()``) when *path*
    is omitted, so query strings never leak into the response body's
    links. The Landmark-Collection lesson #6 made this a repository-wide
    invariant for OGC link builders.
    """
    host = request.get_host().rstrip("/")
    pth = path if path is not None else request.path
    return f"{request.scheme}://{host}{pth}"


def _replace_query(url: str, params: dict[str, Any]) -> str:
    """Return *url* with the query string replaced by *params*.

    Used to build pagination ``rel:next``/``rel:prev`` links that
    preserve the user's original ``bbox``/``datetime``/``limit``
    parameters but update ``offset``.

    The OGC bbox parameter is comma-separated and the datetime parameter
    can contain ``/`` (interval separator), ``:`` (RFC 3339 time), and
    ``.`` (open-end ``..``). RFC 3986 reserves ``,``, ``/``, ``:``, and
    ``.`` as sub-delim / path / unreserved characters that MAY appear
    literally in a query string. Some strict OGC clients (notably
    ArcGIS Pro 3.6 and certain QGIS builds) will reject — or silently
    misparse — pagination links where ``bbox=…%2C…%2C…`` arrives
    percent-encoded. Use ``quote(safe=",.:/")`` to keep these reserved
    characters literal so the round-trip wire form matches what the
    user originally sent.
    """
    parsed = urlparse(url)
    parts: list[str] = []
    for key, value in params.items():
        if value is None:
            continue
        encoded_key = quote(str(key), safe="")
        encoded_value = quote(str(value), safe=",.:/")
        parts.append(f"{encoded_key}={encoded_value}")
    qs = "&".join(parts)
    return urlunparse(parsed._replace(query=qs))


def _items_self_query_params(query: OGCQuery) -> dict[str, Any]:
    """Return normalized representation-changing params for rel:self."""
    return {
        "bbox": (",".join(str(v) for v in query.bbox) if query.bbox else None),
        "datetime": query.datetime_value,
        "limit": str(query.limit) if query.limit_was_supplied else None,
        "offset": (
            str(query.offset)
            if query.offset_was_supplied or query.offset != 0
            else None
        ),
    }


def _items_pagination_query_params(query: OGCQuery) -> dict[str, Any]:
    """Return normalized params that must be preserved on next/prev links."""
    return {
        "bbox": (",".join(str(v) for v in query.bbox) if query.bbox else None),
        "datetime": query.datetime_value,
        "limit": str(query.limit),
    }


# ---------------------------------------------------------------------------
# Envelope builders
# ---------------------------------------------------------------------------


def build_items_envelope(
    *,
    features: list[dict[str, Any]],
    request: Request,
    number_matched: int,
    query: OGCQuery,
) -> dict[str, Any]:
    """Build the OGC FeatureCollection envelope for an ``/items`` response.

    Honours OGC Req 27 (``rel:self``), Req 29 (``timeStamp`` = response
    generation time), and Req 31 (``numberReturned`` = ``len(features)``).
    Includes ``rel:collection`` for breadcrumb navigation and
    ``rel:next``/``rel:prev`` when more pages exist.

    The envelope is built per-request — the caller MUST NOT cache it.
    Caching the timeStamp violates OGC Req 29; caching the self URL
    breaks under proxies that rewrite host/scheme.
    """
    items_url = absolute_url(request)
    self_url = _replace_query(items_url, _items_self_query_params(query))
    # The collection URL is the items URL minus the ``/items`` suffix.
    collection_url = items_url.removesuffix("/items")
    timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    links: list[dict[str, Any]] = [
        {
            "href": self_url,
            "rel": "self",
            "type": "application/geo+json",
            "title": "this document",
        },
        {
            "href": collection_url,
            "rel": "collection",
            "type": "application/json",
            "title": "Collection metadata",
        },
    ]

    existing_qs = _items_pagination_query_params(query)
    if query.offset + query.limit < number_matched:
        next_qs = {
            **existing_qs,
            "offset": str(query.offset + query.limit),
        }
        links.append(
            {
                "href": _replace_query(items_url, next_qs),
                "rel": "next",
                "type": "application/geo+json",
                "title": "Next page",
            }
        )
    if query.offset > 0:
        prev_offset = max(0, query.offset - query.limit)
        prev_qs = {**existing_qs, "offset": str(prev_offset)}
        links.append(
            {
                "href": _replace_query(items_url, prev_qs),
                "rel": "prev",
                "type": "application/geo+json",
                "title": "Previous page",
            }
        )

    return {
        "type": "FeatureCollection",
        "links": links,
        "timeStamp": timestamp,
        "numberMatched": number_matched,
        "numberReturned": len(features),
        "features": features,
    }


def build_single_feature_response(
    *,
    feature: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    """Build the OGC single-feature response.

    Adds OGC ``rel:self`` and ``rel:collection`` links to the feature so
    the response is self-describing per OGC Req 32. Returns a new dict
    without mutating *feature*.
    """
    self_url = absolute_url(request)
    # /items/{featureId} → strip the last two segments to reach the
    # collection metadata URL.
    parts = self_url.rstrip("/").rsplit("/", 2)
    collection_url = parts[0] if len(parts) == _FEATURE_URL_PARTS else self_url

    return {
        **feature,
        "links": [
            {
                "href": self_url,
                "rel": "self",
                "type": "application/geo+json",
                "title": "this document",
            },
            {
                "href": collection_url,
                "rel": "collection",
                "type": "application/json",
                "title": "Collection metadata",
            },
        ],
    }


def build_collection_metadata(
    *,
    collection_id: str,
    title: str,
    description: str,
    request: Request,
    self_path: str,
    items_path: str,
    bbox: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    """Build an OGC API - Features collection metadata document.

    Includes ``crs`` (CRS84 + CRS84h to preserve cave-depth Z values),
    ``storageCrs`` (CRS84h), and an ``extent.spatial.bbox`` reflecting
    the collection's actual geographic footprint when *bbox* is
    supplied. Falls back to :data:`WORLD_BBOX_2D` only when the caller
    has no per-collection bbox to provide — that's the OGC-allowed
    "extent unknown" form, but it makes ArcGIS Pro's auto-zoom land on
    the global view instead of the cave system.

    All four OGC families produce identical-shape collection documents
    via this helper — the only differences are ``id``, ``title``,
    ``description``, the link paths, and ``bbox``.
    """
    host = request.get_host().rstrip("/")
    base = f"{request.scheme}://{host}"
    extent_bbox: list[list[float]]
    if bbox is None:
        extent_bbox = WORLD_BBOX_2D
    else:
        extent_bbox = [[bbox[0], bbox[1], bbox[2], bbox[3]]]
    return {
        "id": collection_id,
        "title": title,
        "description": description,
        "itemType": "feature",
        "crs": [CRS84_2D, CRS84_3D],
        "storageCrs": CRS84_3D,
        "extent": {
            "spatial": {
                "bbox": extent_bbox,
                "crs": CRS84_2D,
            },
        },
        "links": [
            {
                "href": f"{base}{self_path}",
                "rel": "self",
                "type": "application/json",
                "title": title,
            },
            {
                "href": f"{base}{items_path}",
                "rel": "items",
                "type": "application/geo+json",
                "title": f"{title} items",
            },
        ],
    }


def build_landing_page(
    *,
    request: Request,
    title: str,
    description: str,
    collections_path: str,
) -> dict[str, Any]:
    """Build an OGC API - Features landing page response.

    Per OGC §7.2 (Req 2 ``/req/core/root-success``) the landing page
    SHALL advertise ``self``, ``conformance``, ``data``, and either
    ``service-desc`` or ``service-doc`` links so GIS clients can
    discover the service.

    The ``service-desc`` link points at the focused OGC OpenAPI
    document at :data:`OGC_OPENAPI_PATH` —
    a single static document, pre-built once at import time and
    shared by every OGC family. The repository's global
    ``/api/schema/`` endpoint is intentionally NOT used because it
    excludes the OGC routes (those views set ``schema = None``) and
    weighs in at ~684 kB; advertising it would cost every connecting
    client a pointless egress on every connect.
    """
    host = request.get_host().rstrip("/")
    base = f"{request.scheme}://{host}"
    self_path = request.path
    base_path = self_path.rstrip("/")
    return {
        "title": title,
        "description": description,
        "links": [
            {
                "href": f"{base}{self_path}",
                "rel": "self",
                "type": "application/json",
                "title": "This document",
            },
            {
                "href": f"{base}{base_path}/conformance",
                "rel": "conformance",
                "type": "application/json",
                "title": "Conformance declaration",
            },
            {
                "href": f"{base}{collections_path}",
                "rel": "data",
                "type": "application/json",
                "title": "Feature collections",
            },
            {
                "href": f"{base}{OGC_OPENAPI_PATH}",
                "rel": "service-desc",
                "type": "application/vnd.oai.openapi+json;version=3.0",
                "title": "OGC API definition (OpenAPI 3.0)",
            },
        ],
    }


def build_conformance_declaration() -> dict[str, list[str]]:
    """Build an OGC API - Features conformance declaration.

    Single source of truth for ``conformsTo`` so every family's
    ``/conformance`` endpoint advertises an identical, accurate list.
    """
    return {"conformsTo": list(OGC_CONFORMANCE_CLASSES)}


def build_collections_response(
    *,
    request: Request,
    collections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build an OGC API - Features ``/collections`` response.

    *collections* is the list of collection metadata documents already
    produced by :func:`build_collection_metadata`. This function only
    adds the top-level ``links`` envelope.
    """
    self_url = absolute_url(request)
    return {
        "links": [
            {
                "href": self_url,
                "rel": "self",
                "type": "application/json",
                "title": "Feature Collections",
            },
        ],
        "collections": collections,
    }
