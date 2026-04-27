# -*- coding: utf-8 -*-

"""Focused OpenAPI 3.0 document for the SpeleoDB OGC API - Features endpoints.

This module is the **single source** of the API definition advertised
via the ``rel:service-desc`` link on every OGC landing page across all
four families (project view, project user, landmark single, landmark
user).

Why a dedicated document
------------------------

OGC API - Features 1.0 §7.2.4 (Req 2 ``/req/core/root-success``)
mandates that every landing page include a ``service-desc`` (or
``service-doc``) link pointing to the API definition. The repository's
global ``/api/schema/`` endpoint is 684 kB and explicitly omits the
OGC routes (``schema = None`` on every OGC view), so advertising it
is both wasteful and misleading. This module ships a focused
~10-30 kB OpenAPI document covering only the OGC route surface.

Why static + shared
-------------------

The OGC route shape is invariant per-deploy:

* every URL template is fixed (``/view/{gis_token}/...`` etc.);
* the parameter/response/error schemas are the same across all four
  families;
* nothing in the document depends on the request host, scheme, or
  client.

The document is therefore built once at import time, pre-serialised
to canonical bytes via ``orjson``, hashed for ETag, and shared by
every OGC family. The view that serves it advertises a 1-year
``max-age`` so CDNs and clients cache aggressively while still
revalidating against the ETag on the next deploy.
"""

from __future__ import annotations

import hashlib
from typing import Any
from typing import Final

import orjson

from speleodb.gis.ogc_helpers import OGC_CONFORMANCE_CLASSES

# ---------------------------------------------------------------------------
# Path of the service-desc endpoint. Used by ``build_landing_page`` to
# emit the ``rel:service-desc`` link on every OGC landing page.
# ---------------------------------------------------------------------------
OGC_OPENAPI_PATH: Final[str] = "/api/v2/gis-ogc/openapi/"

# ---------------------------------------------------------------------------
# OGC family route shapes — invariant per-deploy.
# ---------------------------------------------------------------------------

# Each family has the same six routes (landing/conformance/collections/
# collection/items/feature) under a different prefix and with one of
# two token parameter names.
_FAMILIES: list[dict[str, str]] = [
    {
        "id": "view",
        "prefix": "/view/{gis_token}",
        "token_param": "gis_token",
        "title": "Project GIS view (gis_token)",
    },
    {
        "id": "user",
        "prefix": "/user/{key}",
        "token_param": "key",
        "title": "Project user (user_token)",
    },
    {
        "id": "landmarkCollection",
        "prefix": "/landmark-collection/{gis_token}",
        "token_param": "gis_token",
        "title": "Landmark single collection (gis_token)",
    },
    {
        "id": "landmarkCollections",
        "prefix": "/landmark-collections/user/{key}",
        "token_param": "key",
        "title": "Landmark collections user (user_token)",
    },
]


# ---------------------------------------------------------------------------
# Reusable component schemas (referenced from every operation).
# ---------------------------------------------------------------------------

_SCHEMAS: dict[str, Any] = {
    "Link": {
        "type": "object",
        "required": ["href", "rel"],
        "properties": {
            "href": {"type": "string", "format": "uri-reference"},
            "rel": {"type": "string"},
            "type": {"type": "string"},
            "title": {"type": "string"},
        },
    },
    "LandingPage": {
        "type": "object",
        "required": ["links"],
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "links": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Link"},
            },
        },
    },
    "ConformanceDeclaration": {
        "type": "object",
        "required": ["conformsTo"],
        "properties": {
            "conformsTo": {
                "type": "array",
                "items": {"type": "string", "format": "uri"},
            },
        },
    },
    "Extent": {
        "type": "object",
        "properties": {
            "spatial": {
                "type": "object",
                "properties": {
                    "bbox": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "minItems": 4,
                            "maxItems": 6,
                            "items": {"type": "number"},
                        },
                    },
                    "crs": {"type": "string"},
                },
            },
        },
    },
    "Collection": {
        "type": "object",
        "required": ["id", "links"],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "itemType": {"type": "string", "default": "feature"},
            "crs": {
                "type": "array",
                "items": {"type": "string", "format": "uri"},
            },
            "storageCrs": {"type": "string", "format": "uri"},
            "extent": {"$ref": "#/components/schemas/Extent"},
            "links": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Link"},
            },
        },
    },
    "Collections": {
        "type": "object",
        "required": ["links", "collections"],
        "properties": {
            "links": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Link"},
            },
            "collections": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Collection"},
            },
        },
    },
    "Geometry": {
        "type": "object",
        "required": ["type"],
        "properties": {
            "type": {
                "type": "string",
                "enum": [
                    "Point",
                    "MultiPoint",
                    "LineString",
                    "MultiLineString",
                    "Polygon",
                    "MultiPolygon",
                    "GeometryCollection",
                ],
            },
            "coordinates": {},
        },
    },
    "Feature": {
        "type": "object",
        "required": ["type", "geometry"],
        "properties": {
            "type": {"type": "string", "enum": ["Feature"]},
            # ``oneOf`` requires exactly one schema to match. ``integer``
            # is a subset of ``number``, so an integer id would match
            # both schemas and violate the ``oneOf`` contract on strict
            # validators. ``anyOf`` (one or more) is the OAS 3.0 idiom
            # for "string or numeric" id types.
            "id": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "number"},
                ],
            },
            "geometry": {
                "nullable": True,
                "allOf": [{"$ref": "#/components/schemas/Geometry"}],
            },
            "properties": {
                "type": "object",
                "nullable": True,
                "additionalProperties": True,
            },
            "links": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Link"},
            },
        },
    },
    "FeatureCollection": {
        "type": "object",
        "required": [
            "type",
            "features",
            "links",
            "timeStamp",
            "numberMatched",
            "numberReturned",
        ],
        "properties": {
            "type": {"type": "string", "enum": ["FeatureCollection"]},
            "features": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Feature"},
            },
            "links": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Link"},
            },
            "timeStamp": {"type": "string", "format": "date-time"},
            "numberMatched": {"type": "integer", "minimum": 0},
            "numberReturned": {"type": "integer", "minimum": 0},
        },
    },
    "Exception": {
        "type": "object",
        "required": ["detail"],
        "properties": {
            "detail": {"type": "string"},
        },
    },
}


# ---------------------------------------------------------------------------
# Reusable parameter components.
# ---------------------------------------------------------------------------

_PARAMETERS: dict[str, Any] = {
    "GisTokenParam": {
        "name": "gis_token",
        "in": "path",
        "required": True,
        "description": "GIS access token (40 hexadecimal characters).",
        "schema": {"type": "string", "pattern": "^[0-9a-fA-F]{40}$"},
    },
    "UserTokenParam": {
        "name": "key",
        "in": "path",
        "required": True,
        "description": "User application token (40 hexadecimal characters).",
        "schema": {"type": "string", "pattern": "^[0-9a-fA-F]{40}$"},
    },
    "CollectionIdParam": {
        "name": "collection_id",
        "in": "path",
        "required": True,
        "description": (
            "Collection identifier. For project endpoints this is a "
            "git commit SHA (6-40 hex chars). For the public Landmark "
            "single-collection endpoint this is the literal "
            "``landmarks``. For Landmark user-token endpoints this is "
            "the LandmarkCollection UUID."
        ),
        "schema": {"type": "string"},
    },
    "FeatureIdParam": {
        "name": "feature_id",
        "in": "path",
        "required": True,
        "description": (
            "Feature identifier. For project endpoints, either the "
            "feature's ``properties.id`` (when present) or the "
            "deterministic synthetic id ``{commit_sha}:{index}``. For "
            "Landmark endpoints, the Landmark UUID."
        ),
        "schema": {"type": "string"},
    },
    "BboxParam": {
        "name": "bbox",
        "in": "query",
        "required": False,
        "description": (
            "Only features that have a geometry that intersects the "
            "bounding box are returned. The bounding box is provided "
            "as four (CRS84) or six (CRS84h) numbers separated by "
            "commas: ``min_lon, min_lat, [min_z,] max_lon, max_lat[, "
            "max_z]``."
        ),
        "schema": {
            "type": "array",
            "minItems": 4,
            "maxItems": 6,
            "items": {"type": "number"},
        },
        "style": "form",
        "explode": False,
    },
    "DatetimeParam": {
        "name": "datetime",
        "in": "query",
        "required": False,
        "description": (
            "Either a date-time or an interval (RFC 3339 §5.6). The "
            "value is validated but cave-survey collections have no "
            "temporal extent, so all features match."
        ),
        "schema": {"type": "string"},
    },
    "LimitParam": {
        "name": "limit",
        "in": "query",
        "required": False,
        "description": (
            "Maximum number of features to return in the response. "
            "Defaults to unlimited (capped at the server maximum). "
            "When set, the response includes a ``rel:next`` link if "
            "more features exist."
        ),
        "schema": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10_000,
        },
    },
    "OffsetParam": {
        "name": "offset",
        "in": "query",
        "required": False,
        "description": (
            "Number of features to skip before returning results. "
            "Combine with ``limit`` for paged retrieval."
        ),
        "schema": {"type": "integer", "minimum": 0},
    },
}


# ---------------------------------------------------------------------------
# Reusable response components.
# ---------------------------------------------------------------------------

_RESPONSES: dict[str, Any] = {
    "LandingPage": {
        "description": "OGC API - Features landing page.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/LandingPage"},
            },
        },
    },
    "ConformanceDeclaration": {
        "description": "OGC API - Features conformance declaration.",
        "content": {
            "application/json": {
                "schema": {
                    "$ref": "#/components/schemas/ConformanceDeclaration",
                },
            },
        },
    },
    "Collections": {
        "description": "OGC API - Features collections list.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Collections"},
            },
        },
    },
    "Collection": {
        "description": "OGC API - Features single-collection metadata.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Collection"},
            },
        },
    },
    "Features": {
        "description": "OGC API - Features GeoJSON FeatureCollection.",
        "content": {
            "application/geo+json": {
                "schema": {"$ref": "#/components/schemas/FeatureCollection"},
            },
        },
    },
    "Feature": {
        "description": "OGC API - Features single Feature.",
        "content": {
            "application/geo+json": {
                "schema": {"$ref": "#/components/schemas/Feature"},
            },
        },
    },
    "BadRequest": {
        "description": "Malformed query parameter (bbox / datetime / limit / offset).",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Exception"},
            },
        },
    },
    "NotFound": {
        "description": "Token, collection, or feature not found.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Exception"},
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Path templates — one entry per OGC endpoint kind. Filled in per-family
# below.
# ---------------------------------------------------------------------------


def _token_param_ref(token_param: str) -> str:
    """Return the ``$ref`` URI for the family's token parameter."""
    return {
        "gis_token": "#/components/parameters/GisTokenParam",
        "key": "#/components/parameters/UserTokenParam",
    }[token_param]


def _build_paths_for(family: dict[str, str]) -> dict[str, Any]:
    """Build the six OGC route entries for a single family."""
    prefix = family["prefix"]
    family_id = family["id"]
    family_title = family["title"]
    token_ref = {"$ref": _token_param_ref(family["token_param"])}
    return {
        f"{prefix}/": {
            "get": {
                "operationId": f"{family_id}LandingPage",
                "summary": f"{family_title} — landing page",
                "tags": [family_title],
                "parameters": [token_ref],
                "responses": {
                    "200": {"$ref": "#/components/responses/LandingPage"},
                    "404": {"$ref": "#/components/responses/NotFound"},
                },
            },
        },
        f"{prefix}/conformance": {
            "get": {
                "operationId": f"{family_id}Conformance",
                "summary": f"{family_title} — conformance declaration",
                "tags": [family_title],
                "parameters": [token_ref],
                "responses": {
                    "200": {
                        "$ref": "#/components/responses/ConformanceDeclaration",
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                },
            },
        },
        f"{prefix}/collections": {
            "get": {
                "operationId": f"{family_id}Collections",
                "summary": f"{family_title} — collections list",
                "tags": [family_title],
                "parameters": [token_ref],
                "responses": {
                    "200": {"$ref": "#/components/responses/Collections"},
                    "404": {"$ref": "#/components/responses/NotFound"},
                },
            },
        },
        f"{prefix}/collections/{{collection_id}}": {
            "get": {
                "operationId": f"{family_id}Collection",
                "summary": f"{family_title} — single collection metadata",
                "tags": [family_title],
                "parameters": [
                    token_ref,
                    {"$ref": "#/components/parameters/CollectionIdParam"},
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/Collection"},
                    "404": {"$ref": "#/components/responses/NotFound"},
                },
            },
        },
        f"{prefix}/collections/{{collection_id}}/items": {
            "get": {
                "operationId": f"{family_id}Items",
                "summary": f"{family_title} — feature items",
                "tags": [family_title],
                "parameters": [
                    token_ref,
                    {"$ref": "#/components/parameters/CollectionIdParam"},
                    {"$ref": "#/components/parameters/BboxParam"},
                    {"$ref": "#/components/parameters/DatetimeParam"},
                    {"$ref": "#/components/parameters/LimitParam"},
                    {"$ref": "#/components/parameters/OffsetParam"},
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/Features"},
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "404": {"$ref": "#/components/responses/NotFound"},
                },
            },
        },
        f"{prefix}/collections/{{collection_id}}/items/{{feature_id}}": {
            "get": {
                "operationId": f"{family_id}Feature",
                "summary": f"{family_title} — single feature",
                "tags": [family_title],
                "parameters": [
                    token_ref,
                    {"$ref": "#/components/parameters/CollectionIdParam"},
                    {"$ref": "#/components/parameters/FeatureIdParam"},
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/Feature"},
                    "404": {"$ref": "#/components/responses/NotFound"},
                },
            },
        },
    }


def _build_spec() -> dict[str, Any]:
    """Build the static OpenAPI 3.0 document (called once at import)."""
    paths: dict[str, Any] = {}
    for family in _FAMILIES:
        paths.update(_build_paths_for(family))
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "SpeleoDB OGC API - Features",
            "description": (
                "Focused OpenAPI definition for the SpeleoDB OGC API - "
                "Features endpoint surface. Documents the four token-"
                "scoped families (project gis-view, project user, "
                "landmark single, landmark user) and their shared "
                "OGC core operations: landing, conformance, "
                "collections, single collection, items, and single "
                "feature."
            ),
            "version": "1.0.0",
            "contact": {
                "name": "SpeleoDB",
                "url": "https://www.speleodb.org/",
            },
            "license": {"name": "GPL-3.0-or-later"},
        },
        "servers": [
            {"url": "/api/v2/gis-ogc", "description": "Same-origin OGC API base"},
        ],
        "tags": [
            {"name": family["title"], "description": family["title"]}
            for family in _FAMILIES
        ],
        "paths": paths,
        "components": {
            "schemas": _SCHEMAS,
            "parameters": _PARAMETERS,
            "responses": _RESPONSES,
        },
        "x-ogc-conformance": OGC_CONFORMANCE_CLASSES,
    }


# ---------------------------------------------------------------------------
# Pre-built artefacts — populated once at import. Every OGC family's
# ``rel:service-desc`` link points to the same URL and every
# ``OGCOpenAPIView.get`` call serves the same bytes.
# ---------------------------------------------------------------------------

OGC_OPENAPI_DOC: Final[dict[str, Any]] = _build_spec()

# Canonical bytes — ``OPT_SORT_KEYS`` makes the byte string stable
# across Python runs so the ETag is deterministic.
OGC_OPENAPI_BYTES: Final[bytes] = orjson.dumps(
    OGC_OPENAPI_DOC,
    option=orjson.OPT_SORT_KEYS,
)

# Strong ETag derived from the document bytes. New deploys only invalidate
# downstream caches when the document content actually changes, otherwise
# clients get a 304 Not Modified.
OGC_OPENAPI_ETAG: Final[str] = f'"{hashlib.sha256(OGC_OPENAPI_BYTES).hexdigest()[:32]}"'

# Cache for one year. Combined with the strong ETag, deploys that change
# the document immediately invalidate the cached entry; deploys that
# don't get a cheap 304.
OGC_OPENAPI_CACHE_CONTROL: Final[str] = "public, max-age=31536000, must-revalidate"

# OGC API - Features Req 6 mandates this content type for the API
# definition.
OGC_OPENAPI_CONTENT_TYPE: Final[str] = "application/vnd.oai.openapi+json;version=3.0"
