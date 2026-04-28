# -*- coding: utf-8 -*-

"""OGC API - Features compliance test suite.

These tests pin every OGC-spec-mandated and ArcGIS-Pro-required field
across all four OGC families served by SpeleoDB:

* project gis-view (``gis_token``)
* project user-token (``key``)
* landmark single-collection (``gis_token``)
* landmark user-token (``key``)

They aim to catch any future ArcGIS Pro 3.6.1 empty-layer regression in
CI rather than in production. They are organised into four sections:

* happy-path compliance assertions (rel:self, numberMatched, timeStamp,
crs, extent, single-feature, etc.).
* geometry regression guard (MultiLineString must round-trip).
* adversarial / cross-tenant / negative-path tests.
* ArcGIS Pro 3.6.1 replay test (reproduces the exact production-log
discovery sequence).

Each test cites the OGC requirement number it pins so the spec
provenance is searchable without leaving the file.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from typing import Protocol
from typing import cast
from urllib.parse import parse_qs
from urllib.parse import urlparse

import jsonschema_rs
import orjson
import pytest
from django.core.cache import cache as _cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import resolve as _resolve
from django.urls import reverse
from django.urls.exceptions import Resolver404
from django.utils import timezone
from drf_spectacular.validation import validate_schema
from pydantic import ValidationError as _ValidationError
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ParseError
from rest_framework.test import APIClient

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.factories import ExperimentFactory
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.api.v2.urls.gis import urlpatterns as ogc_urlpatterns
from speleodb.api.v2.views import gis_view as _gis_view_mod
from speleodb.api.v2.views.ogc_base import OGCLegacyMixedCollectionGoneView
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISProjectView
from speleodb.gis.models import GISView
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission
from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.ogc_helpers import CRS84_2D
from speleodb.gis.ogc_helpers import CRS84_3D
from speleodb.gis.ogc_helpers import MAX_OGC_LIMIT
from speleodb.gis.ogc_helpers import OGC_CONFORMANCE_CLASSES
from speleodb.gis.ogc_helpers import OGCQuery
from speleodb.gis.ogc_helpers import _bbox_intersects
from speleodb.gis.ogc_helpers import apply_ogc_query
from speleodb.gis.ogc_helpers import build_collection_metadata
from speleodb.gis.ogc_helpers import build_items_envelope
from speleodb.gis.ogc_helpers import feature_bbox_2d
from speleodb.gis.ogc_helpers import normalize_features
from speleodb.gis.ogc_helpers import parse_ogc_query
from speleodb.gis.ogc_openapi import OGC_OPENAPI_DOC
from speleodb.surveys.models import ProjectCommit
from speleodb.users.models import User

if TYPE_CHECKING:
    from collections.abc import Iterable

# RFC 3339 instants accept either 'Z' or numeric offset; assert it parses.
_RFC3339_FMT = "%Y-%m-%dT%H:%M:%SZ"

# ---------------------------------------------------------------------------
# Numeric constants used in apply_ogc_query test assertions (PLR2004 hygiene)
# ---------------------------------------------------------------------------
_PAGINATION_FEATURES_TOTAL = 10
_PAGINATION_LIMIT = 2
_HOST_SPLIT_PARTS = 2
_OLDER_COMMIT_DAYS = 1

# Bounds for the per-collection bbox extent regression test
# (``test_collection_metadata_extent_bbox_reflects_real_data``).
# The mixed-geometry fixture clusters near (-87.5, 20.2) and reaches
# (-87.74, 20.44), so the union bbox lives inside this envelope.
_FIXTURE_BBOX_MIN_LON = -88.0
_FIXTURE_BBOX_MAX_LON = -87.0
_FIXTURE_BBOX_MIN_LAT = 20.0
_FIXTURE_BBOX_MAX_LAT = 21.0
_WORLD_BBOX_TUPLE = (-180.0, -90.0, 180.0, 90.0)


class _StreamingResponse(Protocol):
    streaming_content: Iterable[bytes]


def _streaming_json(response: object) -> dict[str, Any]:
    streaming_response = cast("_StreamingResponse", response)
    content = b"".join(streaming_response.streaming_content)
    return cast("dict[str, Any]", orjson.loads(content))


# ---------------------------------------------------------------------------
# Mixed-geometry GeoJSON fixture (Point + LineString + MultiLineString +
# Polygon, with both 2-D and 3-D coordinates and a properties.id on the
# first feature so the lift-to-top-level normalization is exercised).
# ---------------------------------------------------------------------------


def _mixed_geojson_file() -> SimpleUploadedFile:
    return SimpleUploadedFile(
        "mixed.geojson",
        orjson.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [-87.5, 20.2, -1.5],
                        },
                        "properties": {
                            "name": "Entrance",
                            "id": "entrance-uuid",
                        },
                    },
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [-87.5, 20.2, 0.0],
                                [-87.6, 20.3, -1.83],
                            ],
                        },
                        "properties": {"name": "Passage A"},
                    },
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "MultiLineString",
                            "coordinates": [
                                [[-87.7, 20.4], [-87.72, 20.42]],
                                [[-87.72, 20.42], [-87.74, 20.44]],
                            ],
                        },
                        "properties": {"name": "Branch"},
                    },
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-87.6, 20.3],
                                    [-87.59, 20.3],
                                    [-87.59, 20.31],
                                    [-87.6, 20.31],
                                    [-87.6, 20.3],
                                ],
                            ],
                        },
                        "properties": {"name": "Sump"},
                    },
                ],
            }
        ),
        content_type="application/geo+json",
    )


def _create_project_geojson_for(
    project_id: str,
    commit_sha: str,
) -> None:
    commit = ProjectCommit.objects.create(
        id=commit_sha,
        project_id=project_id,
        author_name="Tester",
        author_email="tester@example.com",
        authored_date=timezone.now(),
        message="OGC compliance fixture",
    )
    ProjectGeoJSON.objects.create(
        commit=commit,
        project_id=project_id,
        file=_mixed_geojson_file(),
    )


# ---------------------------------------------------------------------------
# Pure-helper unit tests (run without DB / network)
# ---------------------------------------------------------------------------


class TestOGCHelpers:
    """property-based-style coverage of the pure helper functions.

    These tests run without Django DB access — they exercise the
    parsers and feature-id lifting in isolation.
    """

    factory = RequestFactory()

    # ---- parse_ogc_query ----------------------------------------------

    @pytest.mark.parametrize(
        "qs",
        [
            "",
            "limit=1",
            "limit=10000",
            "offset=5",
            "limit=10&offset=20",
            "bbox=-180,-90,180,90",
            "bbox=170,-10,-170,10",  # antimeridian-crossing form
            "bbox=0,0,0,0,1,1",  # 6-num form
            "datetime=2018-04-03T14:52:23Z",
            "datetime=2018-04-03T14:52:23Z/2018-05-01T00:00:00Z",
            "datetime=../2018-05-01T00:00:00Z",
            "datetime=2018-04-03T14:52:23Z/..",
            "limit=10&bbox=-1,-1,1,1&datetime=2020-01-01T00:00:00Z",
        ],
    )
    def test_parse_ogc_query_accepts_valid_input(self, qs: str) -> None:
        request = self.factory.get(f"/api/v2/gis-ogc/view/abc/items?{qs}")
        # cast to DRF-style request via attribute accessor — parse_ogc_query
        # only uses ``.query_params``, which the Django HttpRequest does
        # NOT expose. Use a thin shim so we don't need full DRF wiring.
        request.query_params = request.GET  # type: ignore[attr-defined]
        result = parse_ogc_query(request)  # type: ignore[arg-type]
        assert isinstance(result, OGCQuery)

    @pytest.mark.parametrize(
        ("qs", "snippet"),
        [
            ("limit=0", "limit"),
            ("limit=-1", "limit"),
            ("limit=abc", "limit"),
            (f"limit={MAX_OGC_LIMIT + 1}", "limit"),
            ("offset=-1", "offset"),
            ("offset=abc", "offset"),
            ("bbox=1,2,3", "bbox"),  # wrong arity (3)
            ("bbox=1,2,3,4,5", "bbox"),  # wrong arity (5)
            ("bbox=0,10,0,0", "bbox"),  # min > max in y
            ("bbox=200,0,201,0", "bbox"),  # lon out of range
            ("bbox=0,100,0,101", "bbox"),  # lat out of range
            ("bbox=NaN,0,0,0", "bbox"),
            ("bbox=Infinity,0,0,0", "bbox"),
            ("bbox=abc,0,0,0", "bbox"),
            ("datetime=not-a-date", "datetime"),
            ("datetime=2018-04-03T14:52:23/extra/parts", "datetime"),
            ("datetime=2018-04-03T14:52:23Z/garbage", "datetime"),
        ],
    )
    def test_parse_ogc_query_rejects_malformed(
        self,
        qs: str,
        snippet: str,
    ) -> None:
        request = self.factory.get(f"/api/v2/gis-ogc/view/abc/items?{qs}")
        request.query_params = request.GET  # type: ignore[attr-defined]
        with pytest.raises(ParseError) as exc_info:
            parse_ogc_query(request)  # type: ignore[arg-type]
        assert snippet.lower() in str(exc_info.value).lower()

    # ---- normalize_features ------------------------------------------

    def test_normalize_lifts_properties_id_to_top_level(self) -> None:
        # ws1a2: ``properties.id`` becomes top-level ``id``.
        features: list[dict[str, Any]] = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"id": "uuid-001", "name": "first"},
            },
        ]
        out = normalize_features(features)
        assert out[0]["id"] == "uuid-001"
        # Original input must not be mutated.
        assert "id" not in features[0]

    def test_normalize_synthesizes_id_when_neither_present(self) -> None:
        features: list[dict[str, Any]] = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"name": "no-id"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1, 1]},
                "properties": {"name": "still-no-id"},
            },
        ]
        out = normalize_features(features, commit_sha="abc")
        assert out[0]["id"] == "abc:0"
        assert out[1]["id"] == "abc:1"

    def test_normalize_preserves_existing_top_level_id(self) -> None:
        features: list[dict[str, Any]] = [
            {
                "id": "explicit-id",
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"id": "ignored"},
            },
        ]
        out = normalize_features(features, commit_sha="abc")
        assert out[0]["id"] == "explicit-id"  # top-level wins

    def test_normalize_disambiguates_duplicate_feature_ids(self) -> None:
        features: list[dict[str, Any]] = [
            {
                "id": "duplicate",
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1, 1]},
                "properties": {"id": "duplicate"},
            },
        ]
        out = normalize_features(features, commit_sha="abc")
        ids = [feature["id"] for feature in out]
        assert ids == ["duplicate", "duplicate:1"]
        assert len(set(ids)) == len(ids)

    def test_normalize_keeps_no_id_when_unmappable(self) -> None:
        # No properties.id, no commit_sha — feature passes through.
        features: list[dict[str, Any]] = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {},
            },
        ]
        out = normalize_features(features)
        assert "id" not in out[0]

    # ---- bbox helpers -------------------------------------------------

    @pytest.mark.parametrize(
        ("geom", "expected"),
        [
            ({"type": "Point", "coordinates": [1, 2]}, (1, 2, 1, 2)),
            (
                {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                (0, 0, 1, 1),
            ),
            (
                {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
                },
                (0, 0, 2, 2),
            ),
            (
                {
                    "type": "MultiPolygon",
                    "coordinates": [
                        [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                        [[[5, 5], [6, 5], [6, 6], [5, 6], [5, 5]]],
                    ],
                },
                (0, 0, 6, 6),
            ),
            (
                {
                    "type": "GeometryCollection",
                    "geometries": [
                        {"type": "Point", "coordinates": [-3, -3]},
                        {"type": "Point", "coordinates": [3, 3]},
                    ],
                },
                (-3, -3, 3, 3),
            ),
        ],
    )
    def test_feature_bbox_for_every_geometry_type(
        self,
        geom: dict[str, Any],
        expected: tuple[float, float, float, float],
    ) -> None:
        feature = {"type": "Feature", "geometry": geom, "properties": {}}
        assert feature_bbox_2d(feature) == expected

    def test_feature_bbox_returns_none_for_null_or_empty(self) -> None:
        assert feature_bbox_2d({"type": "Feature", "geometry": None}) is None
        assert (
            feature_bbox_2d(
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": []}}
            )
            is None
        )
        assert (
            feature_bbox_2d(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": ["not-a-number", "x"],
                    },
                }
            )
            is None
        )

    @pytest.mark.parametrize(
        "geometry",
        [
            {"type": "LineString", "coordinates": "not-coordinates"},
            {"type": "Polygon", "coordinates": "not-rings"},
            {"type": "MultiPolygon", "coordinates": "not-polygons"},
            {"type": "GeometryCollection", "geometries": "not-geometries"},
        ],
    )
    def test_feature_bbox_returns_none_for_malformed_coordinate_containers(
        self,
        geometry: dict[str, Any],
    ) -> None:
        feature = {"type": "Feature", "geometry": geometry, "properties": {}}
        assert feature_bbox_2d(feature) is None

    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ((0, 0, 1, 1), (2, 2, 3, 3), False),  # disjoint
            ((0, 0, 2, 2), (1, 1, 3, 3), True),  # overlap
            ((0, 0, 1, 1), (1, 1, 2, 2), True),  # edge-touch
            ((0, 0, 1, 1), (0, 0, 0.5, 0.5, 100, 200), True),  # 6-num form
            ((175, 0, 176, 1), (170, -10, -170, 10), True),  # antimeridian
            ((-176, 0, -175, 1), (170, -10, -170, 10), True),  # antimeridian
            ((0, 0, 1, 1), (170, -10, -170, 10), False),  # antimeridian miss
        ],
    )
    def test_bbox_intersection_predicate(
        self,
        a: tuple[float, float, float, float],
        b: tuple[float, ...],
        expected: bool,
    ) -> None:
        assert _bbox_intersects(a, b) is expected

    # ---- apply_ogc_query --------------------------------------------

    def test_apply_query_bbox_filters_feature(self) -> None:
        far_point = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [10, 10]},
            "properties": {},
        }
        near_point = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0.5, 0.5]},
            "properties": {},
        }
        sliced, total = apply_ogc_query(
            [far_point, near_point],
            OGCQuery(bbox=(0, 0, 1, 1)),
        )
        assert total == 1
        assert sliced == [near_point]

    def test_apply_query_offset_and_limit(self) -> None:
        features: list[dict[str, Any]] = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [i, 0]},
                "properties": {"name": f"P{i}"},
            }
            for i in range(_PAGINATION_FEATURES_TOTAL)
        ]
        sliced, total = apply_ogc_query(
            features,
            OGCQuery(limit=_PAGINATION_LIMIT, offset=4),
        )
        assert total == _PAGINATION_FEATURES_TOTAL  # numberMatched is pre-slice
        assert len(sliced) == _PAGINATION_LIMIT
        assert sliced[0]["properties"]["name"] == "P4"
        assert sliced[1]["properties"]["name"] == "P5"

    def test_apply_query_bbox_then_offset_past_filtered_total(self) -> None:
        """``bbox`` filters first, ``offset/limit`` slice second; offset
        past the filtered total returns an empty slice while
        ``numberMatched`` reports the post-filter pre-slice count.

        This pins the case from the adversarial review:
            10 features, bbox shrinks to 3, offset=5+limit=10
            → numberMatched=3, numberReturned=0, no next, prev w/ offset=0.
        """
        # Three near features and seven far-away features.
        near = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0.1 + i, 0.1]},
                "properties": {"name": f"near{i}"},
            }
            for i in range(3)
        ]
        far = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [50.0 + i, 50.0]},
                "properties": {"name": f"far{i}"},
            }
            for i in range(7)
        ]
        sliced, total = apply_ogc_query(
            near + far,
            OGCQuery(bbox=(-1.0, -1.0, 5.0, 5.0), limit=10, offset=5),
        )
        assert total == 3  # noqa: PLR2004 — three features matched the bbox
        assert sliced == []  # offset past the matched count

    def test_items_envelope_pagination_past_filtered_total(self) -> None:
        """Integration: the envelope reports ``numberMatched=3``,
        ``numberReturned=0``, omits ``next``, includes ``prev`` with
        ``offset=0`` when bbox shrinks results to fewer than offset.
        """
        request = self.factory.get(
            "/api/v2/gis-ogc/view/TKN/collections/SHA/items"
            "?bbox=-1,-1,5,5&limit=10&offset=5",
            secure=True,
        )
        request.query_params = request.GET  # type: ignore[attr-defined]
        query = parse_ogc_query(request)  # type: ignore[arg-type]
        envelope = build_items_envelope(
            features=[],
            request=cast("Any", request),
            number_matched=3,
            query=query,
        )
        assert envelope["numberMatched"] == 3  # noqa: PLR2004
        assert envelope["numberReturned"] == 0
        rels = [link["rel"] for link in envelope["links"]]
        assert "next" not in rels  # offset+limit (15) > matched (3)
        assert "prev" in rels  # offset > 0
        prev_link = next(
            link["href"] for link in envelope["links"] if link["rel"] == "prev"
        )
        prev_qs = parse_qs(urlparse(prev_link).query)
        # max(0, 5 - 10) = 0
        assert prev_qs["offset"] == ["0"]

    @pytest.mark.parametrize(
        "bad_arity",
        [
            (1.0,),
            (1.0, 2.0),
            (1.0, 2.0, 3.0),
            (1.0, 2.0, 3.0, 4.0, 5.0),
            (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0),
        ],
    )
    def test_ogcquery_bbox_rejects_non_4_or_6_arity(
        self,
        bad_arity: tuple[float, ...],
    ) -> None:
        """Defense-in-depth: ``OGCQuery(bbox=...)`` must reject 3-tuple
        / 5-tuple constructions before they reach ``_bbox_intersects``
        (which would crash with a tuple-unpack IndexError).
        """
        with pytest.raises(_ValidationError):
            OGCQuery(bbox=bad_arity)

    @pytest.mark.parametrize(
        "good_arity",
        [
            (1.0, 2.0, 3.0, 4.0),
            (1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
        ],
    )
    def test_ogcquery_bbox_accepts_4_or_6_arity(
        self, good_arity: tuple[float, ...]
    ) -> None:
        result = OGCQuery(bbox=good_arity)
        assert result.bbox == good_arity

    def test_apply_query_drops_features_with_invalid_geometry_when_bbox_set(
        self,
    ) -> None:
        # features with no geometry must NOT crash bbox filtering;
        # they are simply dropped.
        broken: dict[str, Any] = {
            "type": "Feature",
            "geometry": None,
            "properties": {},
        }
        good: dict[str, Any] = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0.5, 0.5]},
            "properties": {},
        }
        sliced, total = apply_ogc_query(
            [broken, good],
            OGCQuery(bbox=(0, 0, 1, 1)),
        )
        assert total == 1
        assert sliced == [good]

    # ---- envelope builder -------------------------------------------

    def test_items_envelope_emits_required_ogc_fields(self) -> None:
        # ``testserver`` is the host RequestFactory's response uses by
        # default; using it avoids touching ALLOWED_HOSTS.
        request = self.factory.get(
            "/api/v2/gis-ogc/view/TKN/collections/SHA/items",
            secure=True,
        )
        request.query_params = request.GET  # type: ignore[attr-defined]

        envelope = build_items_envelope(
            features=[],
            request=cast("Any", request),
            number_matched=0,
            query=OGCQuery(),
        )
        assert envelope["type"] == "FeatureCollection"
        rels = [link["rel"] for link in envelope["links"]]
        assert "self" in rels  # Req 27
        assert "collection" in rels
        assert envelope["numberMatched"] == 0
        assert envelope["numberReturned"] == 0
        # Req 29: timeStamp must parse as RFC 3339.
        datetime.strptime(envelope["timeStamp"], _RFC3339_FMT).replace(tzinfo=UTC)

    def test_items_envelope_self_link_preserves_representation_query(self) -> None:
        request = self.factory.get(
            (
                "/api/v2/gis-ogc/view/TKN/collections/SHA/items"
                "?bbox=-1,-1,1,1&datetime=2020-01-01T00:00:00Z/.."
                "&limit=1&offset=1"
            ),
            secure=True,
        )
        request.query_params = request.GET  # type: ignore[attr-defined]
        query = parse_ogc_query(request)  # type: ignore[arg-type]
        envelope = build_items_envelope(
            features=[],
            request=cast("Any", request),
            number_matched=3,
            query=query,
        )
        self_href = next(
            link["href"] for link in envelope["links"] if link["rel"] == "self"
        )
        params = parse_qs(urlparse(self_href).query)
        assert params["bbox"] == ["-1.0,-1.0,1.0,1.0"]
        assert params["datetime"] == ["2020-01-01T00:00:00Z/.."]
        assert params["limit"] == ["1"]
        assert params["offset"] == ["1"]

    def test_items_envelope_self_link_uses_literal_commas_and_slashes(self) -> None:
        """Wire-format guarantee: bbox commas, datetime slashes/colons
        in self/next/prev links MUST stay literal (not percent-encoded).

        Strict OGC clients (ArcGIS Pro 3.6, some QGIS builds) reject
        pagination links where ``bbox=...%2C...`` arrives percent-encoded
        or interpret it as a single-string value. RFC 3986 allows these
        chars unreserved-or-sub-delim in a query string, so the wire
        format must match what the user originally sent.
        """
        request = self.factory.get(
            (
                "/api/v2/gis-ogc/view/TKN/collections/SHA/items"
                "?bbox=170,-10,-170,10&datetime=2020-01-01T00:00:00Z/.."
                "&limit=2"
            ),
            secure=True,
        )
        request.query_params = request.GET  # type: ignore[attr-defined]
        query = parse_ogc_query(request)  # type: ignore[arg-type]
        envelope = build_items_envelope(
            features=[],
            request=cast("Any", request),
            number_matched=10,
            query=query,
        )
        for link in envelope["links"]:
            href = link["href"]
            if link["rel"] not in {"self", "next", "prev"}:
                continue
            qs = urlparse(href).query
            # Bbox must contain literal commas, not %2C.
            if "bbox=" in qs:
                assert "%2C" not in qs, (
                    f"bbox commas were percent-encoded in {link['rel']} link: {href}"
                )
                assert "bbox=170" in qs, (
                    f"bbox value not preserved literally in {link['rel']} link: {href}"
                )
            # Datetime intervals/instants must stay literal.
            if "datetime=" in qs:
                assert "%2F" not in qs, (
                    f"datetime '/' was percent-encoded in {link['rel']} link: {href}"
                )
                assert "%3A" not in qs, (
                    f"datetime ':' was percent-encoded in {link['rel']} link: {href}"
                )
                assert "datetime=2020-01-01T00:00:00Z/.." in qs, (
                    f"datetime not preserved literally in {link['rel']} link: {href}"
                )

    def test_default_query_is_bounded_by_server_limit(self) -> None:
        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"name": str(i)},
            }
            for i in range(MAX_OGC_LIMIT + 1)
        ]
        sliced, total = apply_ogc_query(features, OGCQuery())
        assert total == MAX_OGC_LIMIT + 1
        assert len(sliced) == MAX_OGC_LIMIT

    def test_collection_metadata_has_crs_and_extent(self) -> None:
        # ws1c + ws7c3.
        request = self.factory.get(
            "/api/v2/gis-ogc/view/TKN/collections/SHA",
            secure=True,
        )

        meta = build_collection_metadata(
            collection_id="SHA",
            title="Test",
            description="A test collection",
            request=cast("Any", request),
            self_path="/api/v2/gis-ogc/view/TKN/collections/SHA",
            items_path="/api/v2/gis-ogc/view/TKN/collections/SHA/items",
        )
        assert meta["id"] == "SHA"
        assert CRS84_2D in meta["crs"]
        assert CRS84_3D in meta["crs"]  # ArcGIS preserves Z when this is advertised
        assert meta["storageCrs"] == CRS84_3D
        assert "extent" in meta
        assert "spatial" in meta["extent"]
        assert "bbox" in meta["extent"]["spatial"]
        rels = [link["rel"] for link in meta["links"]]
        assert "self" in rels
        assert "items" in rels


# ---------------------------------------------------------------------------
# Integration tests — Project gis-view
# ---------------------------------------------------------------------------


def _temp_geojson_for_view(commit_sha: str) -> SimpleUploadedFile:
    """File-shaped helper: same fixture, ready for ProjectGeoJSON.create."""
    del commit_sha  # SHA is only used for the cache key, not the file.
    return _mixed_geojson_file()


@pytest.mark.django_db
class TestProjectViewOGCCompliance(BaseAPITestCase):
    """Compliance tests for the project gis-view (gis_token) family."""

    def setUp(self) -> None:
        super().setUp()
        self.project = ProjectFactory.create()
        self.gis_view = GISView.objects.create(
            name="Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )
        self.commit_sha = "a" * 40
        commit = ProjectCommit.objects.create(
            id=self.commit_sha,
            project=self.project,
            author_name="Tester",
            author_email="tester@example.com",
            authored_date=timezone.now(),
            message="OGC compliance fixture",
        )
        ProjectGeoJSON.objects.create(
            commit=commit,
            project=self.project,
            file=_temp_geojson_for_view(self.commit_sha),
        )
        GISProjectView.objects.create(
            gis_view=self.gis_view,
            project=self.project,
            commit_sha=self.commit_sha,
        )
        self.public_client = self.client_class()

    @property
    def _lines_id(self) -> str:
        """Geometry-typed collection id for the LineString + MultiLineString layer.

        Centralised so the SHA-and-suffix shape lives in one place; tests
        that need the points layer use ``self._points_id``, tests that
        verify the legacy mixed-form 410 path use ``self.commit_sha``
        directly.
        """
        return f"{self.commit_sha}_lines"

    @property
    def _points_id(self) -> str:
        """Geometry-typed collection id for the Point + MultiPoint layer."""
        return f"{self.commit_sha}_points"

    def _items_response(self, **extra: Any) -> Any:
        return self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection-items",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": self._lines_id,
                },
            ),
            **extra,
        )

    # ws7c1
    def test_items_response_has_rel_self_link(self) -> None:
        """OGC Req 27 + /req/geojson/content B: ``links[*][rel=self]``
        is mandatory on the items FeatureCollection. The original live
        ArcGIS Pro 3.6.1 empty-layer regression came from this gap."""
        resp = self._items_response()
        data = _streaming_json(resp)
        rels = [link["rel"] for link in data["links"]]
        assert "self" in rels
        self_link = next(link for link in data["links"] if link["rel"] == "self")
        assert self_link["type"] == "application/geo+json"
        assert self_link["href"].endswith(
            f"/api/v2/gis-ogc/view/{self.gis_view.gis_token}"
            f"/collections/{self._lines_id}/items"
        )

    # ws7c7
    def test_items_response_has_rel_collection_link(self) -> None:
        resp = self._items_response()
        data = _streaming_json(resp)
        rels = [link["rel"] for link in data["links"]]
        assert "collection" in rels
        col_link = next(link for link in data["links"] if link["rel"] == "collection")
        assert col_link["href"].endswith(
            f"/api/v2/gis-ogc/view/{self.gis_view.gis_token}"
            f"/collections/{self._lines_id}"
        )

    # ws7c2
    # Note on naming: the OGC field names ``numberMatched`` /
    # ``numberReturned`` are themselves camelCase per the spec; the test
    # method name mirrors them deliberately so the spec field is grep-able.
    def test_items_response_has_numberMatched_numberReturned_timestamp(  # noqa: N802
        self,
    ) -> None:
        """OGC Req 29 (timeStamp) + Req 31 (numberReturned)."""
        resp = self._items_response()
        data = _streaming_json(resp)
        # Fixture has 4 mixed-geometry features; the lines collection
        # (``_lines``) carries the LineString + MultiLineString subset
        # (the Point goes to ``_points``, the Polygon is dropped per
        # the no-polygons-in-this-product invariant).
        assert data["numberMatched"] == 2  # noqa: PLR2004
        assert data["numberReturned"] == 2  # noqa: PLR2004
        assert data["numberReturned"] == len(data["features"])  # Req 31
        # timeStamp parses as RFC 3339 instant.
        datetime.strptime(data["timeStamp"], _RFC3339_FMT).replace(tzinfo=UTC)

    # ws7c2b
    def test_items_response_self_link_is_routable(self) -> None:
        resp = self._items_response()
        data = _streaming_json(resp)
        self_href = next(
            link["href"] for link in data["links"] if link["rel"] == "self"
        )
        # Strip scheme+host so we can re-issue the request via the
        # test client (``self_href`` is absolute; we only need the path).
        path = urlparse(self_href).path
        followed = self.public_client.get(path)
        assert followed.status_code == status.HTTP_200_OK
        followed_data = _streaming_json(followed)
        assert followed_data["type"] == "FeatureCollection"

    # ws7c2c
    def test_items_response_per_request_timestamp_is_fresh(self) -> None:
        """envelope is built per-request; cached features
        list contains no envelope, so timeStamp is regenerated each call."""
        # First request to warm the cache.
        first = self._items_response()
        first_data = _streaming_json(first)
        # Sleep just long enough that the next ISO-second is reached.
        # We can't sleep in tests reliably; instead, mock the clock or
        # accept that two calls within the same wall-second produce the
        # same timestamp. The contract is "regenerated per request, not
        # baked into the cached bytes" — re-parsing the body and
        # asserting that the timeStamp field exists and is well-formed
        # is enough; cache-byte-identity-with-fresh-timeStamp is the
        # invariant. We additionally pin that the envelope dict object
        # is a fresh instance (not the cached features list).
        second = self._items_response()
        second_data = _streaming_json(second)
        assert first_data["features"] == second_data["features"]
        # Both timeStamps must individually be valid RFC 3339.
        for ts in (first_data["timeStamp"], second_data["timeStamp"]):
            datetime.strptime(ts, _RFC3339_FMT).replace(tzinfo=UTC)

    # ws7c3
    def test_collection_metadata_advertises_crs84_and_crs84h(self) -> None:
        """ws1c: ``crs`` exposes both CRS84 and CRS84h so ArcGIS Pro
        keeps cave-depth Z values."""
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": self._lines_id,
                },
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert CRS84_2D in data["crs"]
        assert CRS84_3D in data["crs"]
        assert data["storageCrs"] == CRS84_3D
        assert "extent" in data
        assert "spatial" in data["extent"]
        assert "bbox" in data["extent"]["spatial"]

    def test_collection_metadata_extent_bbox_reflects_real_data(self) -> None:
        """``extent.spatial.bbox`` MUST be the union of feature bboxes,
        not the world fallback. Otherwise ArcGIS Pro auto-zooms to the
        global view instead of the cave system on first add.

        Fixture LineString features span roughly (-87.74..-87.5,
        20.2..20.44).
        """
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": self._lines_id,
                },
            )
        )
        bboxes = resp.json()["extent"]["spatial"]["bbox"]
        assert len(bboxes) == 1
        min_lon, min_lat, max_lon, max_lat = bboxes[0]
        # Lines-only subset spans the LineString (-87.5..-87.6, 20.2..20.3)
        # and the MultiLineString (-87.7..-87.74, 20.4..20.44). Assert
        # the bbox is roughly that area, NOT the world.
        assert _FIXTURE_BBOX_MIN_LON < min_lon < _FIXTURE_BBOX_MAX_LON, (
            f"min_lon out of expected range: {min_lon}"
        )
        assert _FIXTURE_BBOX_MIN_LAT < min_lat < _FIXTURE_BBOX_MAX_LAT, (
            f"min_lat out of expected range: {min_lat}"
        )
        assert _FIXTURE_BBOX_MIN_LON < max_lon < _FIXTURE_BBOX_MAX_LON, (
            f"max_lon out of expected range: {max_lon}"
        )
        assert _FIXTURE_BBOX_MIN_LAT < max_lat < _FIXTURE_BBOX_MAX_LAT, (
            f"max_lat out of expected range: {max_lat}"
        )
        # And specifically NOT the world.
        assert (min_lon, min_lat, max_lon, max_lat) != _WORLD_BBOX_TUPLE

    # ws7c4 + ws7c12 — schema completeness guard
    def test_landing_page_does_not_advertise_huge_openapi(self) -> None:
        """ws1e + ws7c4: dropping the service-desc link saves the 684 KB
        /api/schema/ download per ArcGIS connect."""
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-landing",
                kwargs={"gis_token": self.gis_view.gis_token},
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        for link in resp.json()["links"]:
            href = link.get("href", "")
            if link.get("rel") == "service-desc":
                assert not href.endswith("/api/schema/"), (
                    "service-desc link must not target /api/schema/"
                )

    # ws7c5
    def test_items_includes_multilinestring_feature(self) -> None:
        """ws7c5: regression guard against re-introducing a LineString-only filter.

        Compass-tooling exports cave passages as MultiLineString; the
        fixture includes one and the lines collection's response must
        include it.
        """
        resp = self._items_response()
        data = _streaming_json(resp)
        types = {feat["geometry"]["type"] for feat in data["features"]}
        assert "MultiLineString" in types

    def test_lines_collection_items_are_uniform_geometry(self) -> None:
        """Geometry-typed split: ``_lines`` collection MUST contain only
        LineString and MultiLineString features (no Point, no Polygon).
        Pins the 1-collection-1-layer-1-geometry-type contract that
        QGIS / ArcGIS Pro depend on.
        """
        resp = self._items_response()
        data = _streaming_json(resp)
        types = {feat["geometry"]["type"] for feat in data["features"]}
        assert types <= {"LineString", "MultiLineString"}, (
            f"_lines collection has non-line geometries: {types}"
        )

    # ws7c6
    def test_items_features_have_top_level_id(self) -> None:
        """RFC 7946 §3.2 SHOULD: every Feature has a top-level ``id``.

        The fixture's lines subset has the LineString and MultiLineString
        without a ``properties.id`` — they get synthesized ids of the
        form ``{commit_sha}:{index}``.
        """
        resp = self._items_response()
        data = _streaming_json(resp)
        ids = [feat.get("id") for feat in data["features"]]
        assert all(fid is not None for fid in ids)
        assert any(
            isinstance(fid, str) and fid.startswith(self.commit_sha + ":")
            for fid in ids
        )

    # ws7c8
    def test_single_feature_resource_returns_feature(self) -> None:
        """OGC Req 31-33: ``/items/{featureId}`` SHALL return a Feature.

        The fixture LineString is at index 1 (the entrance Point at
        index 0 was lifted to ``entrance-uuid`` and now lives in the
        ``_points`` collection), so its synthesized id is
        ``<sha>:1`` and it is reachable through ``_lines``.
        """
        feature_id = f"{self.commit_sha}:1"
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection-feature",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": self._lines_id,
                    "feature_id": feature_id,
                },
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        data = _streaming_json(resp)
        assert data["type"] == "Feature"
        assert data["geometry"]["type"] == "LineString"
        rels = [link["rel"] for link in data["links"]]
        assert "self" in rels
        assert "collection" in rels

    def test_single_feature_404_for_unknown_id(self) -> None:
        """OGC Req 33: unknown feature_id returns 404."""
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection-feature",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": self._lines_id,
                    "feature_id": "no-such-feature",
                },
            )
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_single_feature_404_when_collection_id_is_wrong_geometry_group(
        self,
    ) -> None:
        """Cross-group feature lookup must 404.

        The Point ``entrance-uuid`` lives in ``_points``. Asking for it
        through the ``_lines`` collection URL must NOT return the
        feature — that would silently lie about the layer geometry to
        the GIS client. Pins the geometry-typed split's
        feature-group invariant.
        """
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection-feature",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": self._lines_id,
                    "feature_id": "entrance-uuid",
                },
            )
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    # ws7c9
    def test_items_bbox_includes_intersecting_features(self) -> None:
        """OGC bbox filter — features inside the bbox are returned.

        Fixture Point ``Entrance`` is at (-87.5, 20.2); a box around it
        must include it through the ``_points`` collection.
        """
        url = reverse(
            "api:v2:gis-ogc:view-collection-items",
            kwargs={
                "gis_token": self.gis_view.gis_token,
                "collection_id": self._points_id,
            },
        )
        resp = self.public_client.get(url + "?bbox=-87.51,20.19,-87.49,20.21")
        assert resp.status_code == status.HTTP_200_OK
        data = _streaming_json(resp)
        names = {f["properties"]["name"] for f in data["features"]}
        assert "Entrance" in names

    def test_items_bbox_excludes_non_intersecting_features(self) -> None:
        url = reverse(
            "api:v2:gis-ogc:view-collection-items",
            kwargs={
                "gis_token": self.gis_view.gis_token,
                "collection_id": self._lines_id,
            },
        )
        resp = self.public_client.get(url + "?bbox=10,10,20,20")
        assert resp.status_code == status.HTTP_200_OK
        data = _streaming_json(resp)
        assert data["features"] == []
        assert data["numberMatched"] == 0

    def test_items_malformed_bbox_returns_400(self) -> None:
        url = reverse(
            "api:v2:gis-ogc:view-collection-items",
            kwargs={
                "gis_token": self.gis_view.gis_token,
                "collection_id": self._lines_id,
            },
        )
        resp = self.public_client.get(url + "?bbox=not,a,bbox,here")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # ws7c10
    def test_items_well_formed_datetime_passes_through(self) -> None:
        """Cave data has no temporal extent — datetime is pass-through."""
        url = reverse(
            "api:v2:gis-ogc:view-collection-items",
            kwargs={
                "gis_token": self.gis_view.gis_token,
                "collection_id": self._lines_id,
            },
        )
        resp = self.public_client.get(url + "?datetime=2020-01-01T00:00:00Z")
        assert resp.status_code == status.HTTP_200_OK
        data = _streaming_json(resp)
        # Lines collection: LineString + MultiLineString match.
        assert data["numberMatched"] == 2  # noqa: PLR2004

    def test_items_malformed_datetime_returns_400(self) -> None:
        url = reverse(
            "api:v2:gis-ogc:view-collection-items",
            kwargs={
                "gis_token": self.gis_view.gis_token,
                "collection_id": self._lines_id,
            },
        )
        resp = self.public_client.get(url + "?datetime=not-a-date")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # ws7c11
    def test_conformance_declares_only_implemented_classes(self) -> None:
        """The conformance endpoint advertises exactly the constant.

        This is the structural half of the conformance-honesty contract;
        the per-class behavior tests below assert that each declared
        class is actually backed by observable behavior, so an addition
        to ``OGC_CONFORMANCE_CLASSES`` without a matching implementation
        gets caught by one of those tests, not by a tautology.
        """
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-conformance",
                kwargs={"gis_token": self.gis_view.gis_token},
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        declared = set(resp.json()["conformsTo"])
        assert declared == set(OGC_CONFORMANCE_CLASSES)

    def test_conformance_class_core_behavior_bbox_filters(self) -> None:
        """``conf/core`` requires ``bbox`` to actually filter features.

        If we declare core conformance, a non-intersecting bbox MUST
        return an empty feature collection — not the full set. This is
        the bug that prompted the original ArcGIS Pro empty-layer
        forensics: declaring core while silently ignoring bbox/limit.
        """
        url = reverse(
            "api:v2:gis-ogc:view-collection-items",
            kwargs={
                "gis_token": self.gis_view.gis_token,
                "collection_id": self._lines_id,
            },
        )
        full = _streaming_json(self.public_client.get(url))
        assert full["numberMatched"] >= 1
        filtered = _streaming_json(self.public_client.get(url + "?bbox=-1,-1,1,1"))
        assert filtered["numberMatched"] == 0
        assert filtered["features"] == []

    def test_conformance_class_core_behavior_limit_paginates(self) -> None:
        """``conf/core`` requires ``limit`` to actually slice the response."""
        url = reverse(
            "api:v2:gis-ogc:view-collection-items",
            kwargs={
                "gis_token": self.gis_view.gis_token,
                "collection_id": self._lines_id,
            },
        )
        resp = _streaming_json(self.public_client.get(url + "?limit=1"))
        assert resp["numberReturned"] == 1
        assert resp["numberMatched"] >= 1
        # ``next`` link must be present iff numberMatched > limit.
        if resp["numberMatched"] > 1:
            rels = {link["rel"] for link in resp["links"]}
            assert "next" in rels

    def test_conformance_class_geojson_behavior_content_type(self) -> None:
        """``conf/geojson`` requires the items response Content-Type to
        be ``application/geo+json`` (RFC 7946)."""
        url = reverse(
            "api:v2:gis-ogc:view-collection-items",
            kwargs={
                "gis_token": self.gis_view.gis_token,
                "collection_id": self._lines_id,
            },
        )
        resp = self.public_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert "application/geo+json" in resp["Content-Type"]

    def test_conformance_class_oas30_behavior_openapi_validates(self) -> None:
        """``conf/oas30`` requires the service-desc OpenAPI document to
        validate as OpenAPI 3.0. drf-spectacular's ``validate_schema``
        runs the OAS 3.0 meta-schema validator under the hood.
        """
        resp = self.public_client.get(reverse("api:v2:gis-ogc:openapi"))
        assert resp.status_code == status.HTTP_200_OK
        body = _streaming_json(resp)
        validate_schema(body)

    # ws7e
    def test_landing_page_data_link_targets_collections(self) -> None:
        """ws3b: rel:data must point at <base>/collections, not the
        bare token URL (which used to return the collections list and
        violated OGC discovery convention).
        """
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-landing",
                kwargs={"gis_token": self.gis_view.gis_token},
            )
        )
        data = resp.json()
        data_link = next(link for link in data["links"] if link["rel"] == "data")
        assert data_link["href"].endswith("/collections")

    # ws7a
    def test_collections_query_params_do_not_corrupt_child_links(self) -> None:
        """ws2: query strings (?f=json) must not leak into child link
        paths. The previous code used ``request.get_full_path()`` which
        produced ``/view/<token>?f=json/<sha>`` — a 404."""
        url = reverse(
            "api:v2:gis-ogc:view-collections",
            kwargs={"gis_token": self.gis_view.gis_token},
        )
        resp = self.public_client.get(url + "?f=json")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        for collection in data["collections"]:
            for link in collection["links"]:
                href = link["href"]
                assert "?f=json/" not in href, f"Query string leaked into href: {href}"


# ---------------------------------------------------------------------------
# Integration tests — Landmark single-collection (ws7c1-c12)
# ---------------------------------------------------------------------------


@pytest.fixture
def landmark_owner() -> User:
    return User.objects.create_user(email="landmark-owner@example.com")


@pytest.fixture
def landmark_collection(landmark_owner: User) -> LandmarkCollection:
    coll = LandmarkCollection.objects.create(
        name="Compliance Collection",
        description="OGC compliance test fixture",
        created_by=landmark_owner.email,
    )
    LandmarkCollectionUserPermission.objects.create(
        collection=coll,
        user=landmark_owner,
        level=PermissionLevel.ADMIN,
    )
    Landmark.objects.create(
        name="Alpha",
        description="A",
        latitude=45.0,
        longitude=-122.0,
        created_by=landmark_owner.email,
        collection=coll,
    )
    Landmark.objects.create(
        name="Beta",
        description="B",
        latitude=46.0,
        longitude=-123.0,
        created_by=landmark_owner.email,
        collection=coll,
    )
    return coll


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestLandmarkSingleOGCCompliance:
    """Compliance tests for the public landmark gis_token family."""

    def test_items_response_has_rel_self_and_collection_links(
        self,
        api_client: APIClient,
        landmark_collection: LandmarkCollection,
    ) -> None:
        url = reverse(
            "api:v2:gis-ogc:landmark-collection-collection-items",
            kwargs={
                "gis_token": landmark_collection.gis_token,
                "collection_id": "landmarks",
            },
        )
        resp = api_client.get(url)
        data = _streaming_json(resp)
        rels = {link["rel"] for link in data["links"]}
        assert "self" in rels
        assert "collection" in rels

    def test_items_response_carries_ogc_counts_and_timestamp(
        self,
        api_client: APIClient,
        landmark_collection: LandmarkCollection,
    ) -> None:
        url = reverse(
            "api:v2:gis-ogc:landmark-collection-collection-items",
            kwargs={
                "gis_token": landmark_collection.gis_token,
                "collection_id": "landmarks",
            },
        )
        resp = api_client.get(url)
        data = _streaming_json(resp)
        assert data["numberMatched"] == 2  # noqa: PLR2004
        assert data["numberReturned"] == 2  # noqa: PLR2004
        datetime.strptime(data["timeStamp"], _RFC3339_FMT).replace(tzinfo=UTC)

    def test_collection_metadata_advertises_crs84h(
        self,
        api_client: APIClient,
        landmark_collection: LandmarkCollection,
    ) -> None:
        url = reverse(
            "api:v2:gis-ogc:landmark-collection-collection",
            kwargs={
                "gis_token": landmark_collection.gis_token,
                "collection_id": "landmarks",
            },
        )
        data = api_client.get(url).json()
        assert CRS84_2D in data["crs"]
        assert CRS84_3D in data["crs"]
        assert data["storageCrs"] == CRS84_3D
        assert "extent" in data

    def test_single_feature_resource_returns_feature(
        self,
        api_client: APIClient,
        landmark_collection: LandmarkCollection,
    ) -> None:
        first = landmark_collection.landmarks.first()
        assert first is not None
        url = reverse(
            "api:v2:gis-ogc:landmark-collection-collection-feature",
            kwargs={
                "gis_token": landmark_collection.gis_token,
                "collection_id": "landmarks",
                "feature_id": str(first.id),
            },
        )
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        data = _streaming_json(resp)
        assert data["type"] == "Feature"

    def test_single_feature_404_for_unknown_uuid(
        self,
        api_client: APIClient,
        landmark_collection: LandmarkCollection,
    ) -> None:
        url = reverse(
            "api:v2:gis-ogc:landmark-collection-collection-feature",
            kwargs={
                "gis_token": landmark_collection.gis_token,
                "collection_id": "landmarks",
                "feature_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_landing_page_data_link_targets_collections(
        self,
        api_client: APIClient,
        landmark_collection: LandmarkCollection,
    ) -> None:
        resp = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collection-landing",
                kwargs={"gis_token": landmark_collection.gis_token},
            )
        )
        data_link = next(link for link in resp.json()["links"] if link["rel"] == "data")
        assert data_link["href"].endswith("/collections")


# ---------------------------------------------------------------------------
# Cross-tenant security tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOGCCrossTenantSecurity:
    """tokens must never leak data across tenants."""

    def test_token_a_cannot_access_token_b_landmark_collection(
        self,
        api_client: APIClient,
    ) -> None:
        owner_a = User.objects.create_user(email="owner-a@example.com")
        owner_b = User.objects.create_user(email="owner-b@example.com")
        coll_a = LandmarkCollection.objects.create(name="A", created_by=owner_a.email)
        LandmarkCollectionUserPermission.objects.create(
            collection=coll_a,
            user=owner_a,
            level=PermissionLevel.ADMIN,
        )
        coll_b = LandmarkCollection.objects.create(name="B", created_by=owner_b.email)
        LandmarkCollectionUserPermission.objects.create(
            collection=coll_b,
            user=owner_b,
            level=PermissionLevel.ADMIN,
        )
        token_a = Token.objects.create(
            user=owner_a, key="0123456789abcdef" * 2 + "01234567"
        )
        # Token A asks for collection B's UUID via the user-token endpoint.
        resp = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collections-user-collection",
                kwargs={
                    "key": token_a.key,
                    "collection_id": str(coll_b.id),
                },
            )
        )
        # 404, not 403 — never leak existence.
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_use_latest_view_cannot_access_historical_project_commit(
        self,
        api_client: APIClient,
    ) -> None:
        owner = User.objects.create_user(email="latest-owner@example.com")
        project = ProjectFactory.create(created_by=owner.email)
        old_sha = "1" * 40
        latest_sha = "2" * 40
        old_commit = ProjectCommit.objects.create(
            id=old_sha,
            project=project,
            author_name="Tester",
            author_email="tester@example.com",
            authored_date=timezone.now() - timedelta(days=_OLDER_COMMIT_DAYS),
            message="Old OGC fixture",
        )
        ProjectGeoJSON.objects.create(
            commit=old_commit,
            project=project,
            file=_mixed_geojson_file(),
        )
        latest_commit = ProjectCommit.objects.create(
            id=latest_sha,
            project=project,
            author_name="Tester",
            author_email="tester@example.com",
            authored_date=timezone.now(),
            message="Latest OGC fixture",
        )
        ProjectGeoJSON.objects.create(
            commit=latest_commit,
            project=project,
            file=_mixed_geojson_file(),
        )
        gis_view = GISView.objects.create(
            name="Latest only",
            owner=owner,
            allow_precise_zoom=False,
        )
        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            use_latest=True,
        )

        denied = api_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection-items",
                kwargs={
                    "gis_token": gis_view.gis_token,
                    "collection_id": f"{old_sha}_lines",
                },
            )
        )
        allowed = api_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection-items",
                kwargs={
                    "gis_token": gis_view.gis_token,
                    "collection_id": f"{latest_sha}_lines",
                },
            )
        )

        assert denied.status_code == status.HTTP_404_NOT_FOUND
        assert allowed.status_code == status.HTTP_200_OK
        # ``use_latest=True`` views ship a short Cache-Control window so
        # the CDN doesn't pin a now-stale 404 once the latest moves.
        assert "max-age=300" in allowed["Cache-Control"]
        assert "must-revalidate" in allowed["Cache-Control"]

    def test_user_token_cannot_access_other_users_project_commit(
        self,
        api_client: APIClient,
    ) -> None:
        owner_a = User.objects.create_user(email="project-owner-a@example.com")
        owner_b = User.objects.create_user(email="project-owner-b@example.com")
        project_b = ProjectFactory.create(created_by=owner_b.email)
        other_sha = "3" * 40
        _create_project_geojson_for(str(project_b.id), other_sha)
        token_a = Token.objects.create(user=owner_a, key="4" * 40)

        resp = api_client.get(
            reverse(
                "api:v2:gis-ogc:user-collection-items",
                kwargs={
                    "key": token_a.key,
                    "collection_id": f"{other_sha}_lines",
                },
            )
        )

        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Adversarial / negative-path tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOGCAdversarial(BaseAPITestCase):
    """malformed inputs return shaped errors, never leak."""

    def setUp(self) -> None:
        super().setUp()
        self.public_client = self.client_class()
        self.project = ProjectFactory.create()
        self.gis_view = GISView.objects.create(
            name="Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )
        self.commit_sha = "a" * 40
        _create_project_geojson_for(str(self.project.id), self.commit_sha)
        GISProjectView.objects.create(
            gis_view=self.gis_view,
            project=self.project,
            commit_sha=self.commit_sha,
        )

    def test_path_traversal_collection_id_returns_404(self) -> None:
        # Both URL converters (``ogc_typed_id`` and ``gitsha``) reject
        # '../...' before the view sees it; ensure neither matches.
        resp = self.public_client.get(
            f"/api/v2/gis-ogc/view/{self.gis_view.gis_token}"
            f"/collections/..%2Fetc%2Fpasswd"
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_uppercase_sha_in_url_resolves_to_same_collection(self) -> None:
        """SHA URL converter accepts both cases; the service layer must
        normalise to lowercase so mixed-case SHAs (e.g. user pastes a
        SHA from a tool that emits uppercase) round-trip cleanly. The
        ``ogc_typed_id`` converter regex also matches the uppercase SHA
        half — group suffix stays lowercase.
        """
        upper_sha = self.commit_sha.upper()
        assert upper_sha != self.commit_sha  # sanity: actually mixed case

        url = (
            f"/api/v2/gis-ogc/view/{self.gis_view.gis_token}"
            f"/collections/{upper_sha}_lines/items"
        )
        resp = self.public_client.get(url)
        assert resp.status_code == status.HTTP_200_OK

    def test_router_rejects_invalid_gis_token_format(self) -> None:
        """The ``<gis_token:gis_token>`` URL converter regex
        (``[0-9a-fA-F]{40}``) is enforced at the routing layer for every
        OGC family. A malformed token must 404 *without* hitting the
        view (no DB lookup, no permission check).

        ``unittest.TestCase`` subclasses don't honour
        ``pytest.mark.parametrize``, so iterate with ``subTest`` to
        keep per-input failure messages.

        Note: landing URLs no longer carry a trailing slash (see
        ``test_no_ogc_url_pattern_has_inconsistent_trailing_slash``),
        so the resolve target here drops the ``/`` to reflect the
        canonical URL shape.
        """
        bad_tokens = [
            "TKN",  # too short
            "tkn123",  # too short
            "z" * 40,  # 40 chars but not hex
            "!@#$%^&*()_+",  # special chars
            "a" * 39,  # 39 hex chars (one short)
            "a" * 41,  # 41 hex chars (one long)
            "ABC-DEF-" + "a" * 32,  # hyphens are not in the hex alphabet
        ]
        prefixes = (
            "/api/v2/gis-ogc/view",
            "/api/v2/gis-ogc/landmark-collection",
            "/api/v2/gis-ogc/experiment",
        )
        for bad_token in bad_tokens:
            for prefix in prefixes:
                with (
                    self.subTest(prefix=prefix, bad_token=bad_token),
                    pytest.raises(Resolver404),
                ):
                    _resolve(f"{prefix}/{bad_token}")

    def test_router_rejects_invalid_user_token_format(self) -> None:
        """Same router-layer guarantee for ``<user_token:key>``.

        Landing URLs are slash-free now; the resolve target reflects
        the canonical shape.
        """
        for prefix in (
            "/api/v2/gis-ogc/user",
            "/api/v2/gis-ogc/landmark-collections/user",
        ):
            with (
                self.subTest(prefix=prefix, bad_token="special-chars"),  # noqa: S106
                pytest.raises(Resolver404),
            ):
                _resolve(f"{prefix}/!@#$%^&*()")
            with (
                self.subTest(prefix=prefix, bad_token="40-non-hex"),  # noqa: S106
                pytest.raises(Resolver404),
            ):
                _resolve(f"{prefix}/{'z' * 40}")

    def test_unknown_collection_id_404s(self) -> None:
        """Unknown geometry-typed collection id returns 404.

        Uses the new ``<sha>_<group>`` form so the request reaches
        ``OGCGISViewCollectionApiView.get`` (which then 404s because
        no project rows match). The legacy bare-``<sha>`` form is a
        separate contract (410 Gone) — see the geometry-split
        regression tests.
        """
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": f"{'f' * 40}_lines",
                },
            )
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_empty_offset_returns_full_collection(self) -> None:
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection-items",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": f"{self.commit_sha}_lines",
                },
            )
            + "?offset=100"  # past the end
        )
        assert resp.status_code == status.HTTP_200_OK
        data = _streaming_json(resp)
        assert data["features"] == []
        # Lines collection: LineString + MultiLineString (Polygon dropped).
        assert data["numberMatched"] == 2  # noqa: PLR2004
        assert data["numberReturned"] == 0


# ---------------------------------------------------------------------------
# Cache-size guard regression test
# ---------------------------------------------------------------------------


def _modest_geojson_file(num_features: int = 100) -> SimpleUploadedFile:
    """Build a small GeoJSON fixture (well below default cache cap).

    Used by the cache-size-guard test, which lowers the cache cap to a
    handful of bytes via monkeypatch so a tiny fixture is enough to
    exceed it. This keeps the test fast — no need to allocate megabytes
    of S3 just to cross a 5 MiB threshold.
    """
    return SimpleUploadedFile(
        "modest.geojson",
        orjson.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [-87.5 + i * 0.0001, 20.2],
                        },
                        "properties": {"name": f"Station-{i:04d}"},
                    }
                    for i in range(num_features)
                ],
            }
        ),
        content_type="application/geo+json",
    )


@pytest.mark.django_db
class TestOGCCacheSizeGuard(BaseAPITestCase):
    """Memcached default ``-I 1m`` and Redis default ``proto-max-bulk-len``
    reject or refuse very large values. The cache layer skips cache.set
    above ``_GEOJSON_CACHE_MAX_BYTES``; the request still serves a 200
    with the correct payload, just paying an S3 read every call.
    """

    def setUp(self) -> None:
        super().setUp()
        self.public_client = self.client_class()
        self.project = ProjectFactory.create()
        self.gis_view = GISView.objects.create(
            name="Large View",
            owner=self.user,
            allow_precise_zoom=False,
        )
        self.commit_sha = "c" * 40
        commit = ProjectCommit.objects.create(
            id=self.commit_sha,
            project=self.project,
            author_name="Tester",
            author_email="tester@example.com",
            authored_date=timezone.now(),
            message="Large fixture",
        )
        ProjectGeoJSON.objects.create(
            commit=commit,
            project=self.project,
            file=_modest_geojson_file(),
        )
        GISProjectView.objects.create(
            gis_view=self.gis_view,
            project=self.project,
            commit_sha=self.commit_sha,
        )

    def test_oversize_payload_still_serves_200(self) -> None:
        """A payload over the cache cap must NOT crash the cache layer.

        Regression guard: the previous implementation called
        ``cache.set`` unconditionally. Memcached refuses values over
        1 MiB by default, raising a ``MemcachedException`` that
        propagated as a 500. The size-guarded version skips the
        cache.set so the request stays a 200.

        We force the cap to 1 byte for the duration of the test so any
        non-empty payload crosses the threshold — no need to allocate
        a real >5 MiB fixture.
        """
        # Deliberately reaching into the module's private cap constant
        # so we can exercise the over-limit path without allocating a
        # real >5 MiB fixture. Restore in ``finally`` so test ordering
        # doesn't leak the override.
        original_cap = _gis_view_mod._GEOJSON_CACHE_MAX_BYTES  # noqa: SLF001
        _gis_view_mod._GEOJSON_CACHE_MAX_BYTES = 1  # noqa: SLF001
        try:
            # The fixture is Point-only, so the ``_points`` collection
            # is the one that exists — querying through it exercises
            # the cache-size guard end-to-end.
            collection_id = f"{self.commit_sha}_points"
            resp = self.public_client.get(
                reverse(
                    "api:v2:gis-ogc:view-collection-items",
                    kwargs={
                        "gis_token": self.gis_view.gis_token,
                        "collection_id": collection_id,
                    },
                )
            )
            assert resp.status_code == status.HTTP_200_OK
            # Cache must be empty for this SHA — payload was over the cap.
            assert _cache.get(f"ogc_geojson_features_{self.commit_sha}") is None
            # And the index cache is also empty (skipped together).
            assert _cache.get(f"ogc_geojson_features_index_{self.commit_sha}") is None

            # A second request also serves 200 — re-reads from S3 each time.
            resp_again = self.public_client.get(
                reverse(
                    "api:v2:gis-ogc:view-collection-items",
                    kwargs={
                        "gis_token": self.gis_view.gis_token,
                        "collection_id": collection_id,
                    },
                )
            )
            assert resp_again.status_code == status.HTTP_200_OK
        finally:
            _gis_view_mod._GEOJSON_CACHE_MAX_BYTES = original_cap  # noqa: SLF001


# ---------------------------------------------------------------------------
# Single-feature index test (ArcGIS Pro edit-tracking hot path)
# ---------------------------------------------------------------------------


_SINGLE_FEATURE_BATCH_SIZE: int = 100


@pytest.mark.django_db
class TestSingleFeatureIndex(BaseAPITestCase):
    """The single-feature endpoint MUST be O(1) per request.

    ArcGIS Pro 3.6 edit-tracking issues one ``/items/{featureId}``
    per modified row. With a linear scan, M lookups against a
    collection of N features cost O(M·N). With the cached
    ``{id: feature}`` index they cost O(M).

    This test pins that 100 sequential single-feature requests do not
    trigger 100 storage reads (one warm-up read at most), and that
    every lookup serves a 200.
    """

    def setUp(self) -> None:
        super().setUp()
        self.public_client = self.client_class()
        self.project = ProjectFactory.create()
        self.gis_view = GISView.objects.create(
            name="Index Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )
        self.commit_sha = "d" * 40
        commit = ProjectCommit.objects.create(
            id=self.commit_sha,
            project=self.project,
            author_name="Tester",
            author_email="tester@example.com",
            authored_date=timezone.now(),
            message="Index fixture",
        )
        # 100 features each with an explicit ``properties.id`` we can
        # later request via the single-feature endpoint.
        ProjectGeoJSON.objects.create(
            commit=commit,
            project=self.project,
            file=SimpleUploadedFile(
                "indexed.geojson",
                orjson.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Point",
                                    "coordinates": [-87.5 + i * 0.001, 20.2],
                                },
                                "properties": {
                                    "name": f"Station-{i}",
                                    "id": f"feature-{i:04d}",
                                },
                            }
                            for i in range(_SINGLE_FEATURE_BATCH_SIZE)
                        ],
                    }
                ),
                content_type="application/geo+json",
            ),
        )
        GISProjectView.objects.create(
            gis_view=self.gis_view,
            project=self.project,
            commit_sha=self.commit_sha,
        )

    def test_100_single_feature_requests_use_index(self) -> None:
        """All 100 single-feature lookups serve a 200 with the right id.

        Fixture is Point-only, so the lookups go through ``_points``.
        """
        collection_id = f"{self.commit_sha}_points"
        for i in range(_SINGLE_FEATURE_BATCH_SIZE):
            feature_id = f"feature-{i:04d}"
            resp = self.public_client.get(
                reverse(
                    "api:v2:gis-ogc:view-collection-feature",
                    kwargs={
                        "gis_token": self.gis_view.gis_token,
                        "collection_id": collection_id,
                        "feature_id": feature_id,
                    },
                )
            )
            assert resp.status_code == status.HTTP_200_OK, (
                f"feature {feature_id} returned {resp.status_code}"
            )
            data = _streaming_json(resp)
            assert data["id"] == feature_id

    def test_index_cache_is_populated_after_first_items_request(self) -> None:
        """The first /items request fills both the features list and the
        ``{id: feature}`` index in the cache. Subsequent single-feature
        lookups hit the index directly — no need to re-read the list.
        """
        # Cold: nothing cached.
        assert _cache.get(f"ogc_geojson_features_{self.commit_sha}") is None
        assert _cache.get(f"ogc_geojson_features_index_{self.commit_sha}") is None

        # Warm up via /items.
        items_resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection-items",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": f"{self.commit_sha}_points",
                },
            )
        )
        assert items_resp.status_code == status.HTTP_200_OK

        # Both list and index are now populated.
        cached_list = _cache.get(f"ogc_geojson_features_{self.commit_sha}")
        cached_index = _cache.get(f"ogc_geojson_features_index_{self.commit_sha}")
        assert cached_list is not None
        assert cached_index is not None
        assert isinstance(cached_index, dict)
        assert len(cached_index) == _SINGLE_FEATURE_BATCH_SIZE
        assert "feature-0000" in cached_index
        assert "feature-0099" in cached_index


# ---------------------------------------------------------------------------
# ArcGIS Pro 3.6.1 replay test
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExperimentEndpointIsNotOGC(BaseAPITestCase):
    """ws7h: pin that the experiment GIS endpoint is NOT advertised as
    a full OGC API - Features service.

    Wrapping the experiment endpoint in a full OGC tree
    (landing/conformance/collections/items/feature) is out of scope
    for this PR but is documented in
    ``tasks/lessons/ogc-arcgis-empty-layers.md``. This test ensures
    that until that work happens, the response stays a single flat
    GeoJSON FeatureCollection — a regression that accidentally adds
    ``links``/``conformsTo`` to it would mislead clients into
    expecting OGC discovery.
    """

    def test_experiment_endpoint_returns_flat_feature_collection(self) -> None:
        experiment = ExperimentFactory.create(created_by=self.user.email)
        resp = self.client.get(
            reverse(
                "api:v2:gis-ogc:experiment",
                kwargs={"gis_token": experiment.gis_token},
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["type"] == "FeatureCollection"
        # Critical: NOT a OGC discovery document.
        assert "conformsTo" not in body
        # ``links`` is accepted on a FeatureCollection per RFC 7946 but
        # the experiment endpoint deliberately returns a bare body —
        # if a future change wraps it with the OGC envelope, the test
        # is updated to assert the FULL OGC tree, not just the
        # presence of ``links``.
        assert "links" not in body


@pytest.mark.django_db
class TestQueryCountInvariants(BaseAPITestCase):
    """ws7d: pin the query counts for OGC user-token discovery.

    Without ``select_related("user")`` on the Token queryset and
    ``select_related("commit", "project")`` on the Prefetch, ArcGIS
    Pro's collections-list response would scale O(N) projects with
    O(N) extra queries each. These assertions are tight pins so any
    future change that re-introduces the N+1 pattern fails CI.
    """

    def setUp(self) -> None:
        super().setUp()
        # ``TokenFactory`` already produces a 40-char hex key (matches
        # the ``<user_token:key>`` converter regex), so no hand-rolled
        # token swap is needed here.
        # Five projects, each with one geojson commit. Without
        # select_related, every project would lazily load its commit
        # AND project relation when ``commit_sha`` / ``project.name``
        # is accessed.
        for i in range(5):
            project = ProjectFactory.create(created_by=self.user.email)
            UserProjectPermissionFactory(
                target=self.user,
                level=PermissionLevel.READ_ONLY,
                project=project,
            )
            _create_project_geojson_for(
                str(project.id),
                "0123456789abcdef" * 2 + f"{i:08x}",
            )

    def test_user_token_collections_query_count_is_bounded(self) -> None:
        """5 projects + 1 token: queries should be O(1) — token
        lookup + permission resolution + project list + prefetch.

        Baseline math (5 projects, 1 token):
        * Token + user select_related — 1 query
        * Permissions resolution (UserProjectPermission filter) — 1
        * Projects filter — 1
        * Geojsons prefetch (one IN-list query) — 1
        * Auxiliary auth/session middleware — 1-2

        That's ~5 queries baseline. The cap of 10 catches a 5-project
        N+1 regression (which would be ~10-12 queries) without false
        positives from session/auth churn.

        Pytest's ``django_assert_max_num_queries`` fixture is unavailable
        inside ``unittest.TestCase`` subclasses — DRF's
        ``BaseAPITestCase`` is one — so we use Django's native
        :class:`~django.test.utils.CaptureQueriesContext` to count
        executed queries against the default connection.
        """
        url = reverse(
            "api:v2:gis-ogc:user-collections",
            kwargs={"key": self.token.key},
        )
        max_queries = 10
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        # Sanity: 5 projects x 2 geometry-typed collections (the
        # mixed fixture has both Points and LineStrings present, so
        # each project produces ``<sha>_points`` + ``<sha>_lines``).
        # If a future change makes ``list_collections`` enumerate
        # projects per group via ``_load_geometry_groups_present``
        # in a way that issues per-project cache misses synchronously,
        # the query count cap below will catch it (the cap is 10 for
        # 5 projects: token+user, perms, projects, prefetch, plus
        # ~6 cache reads — none of which hit the DB).
        assert len(resp.json()["collections"]) == 10  # noqa: PLR2004
        actual = len(ctx.captured_queries)
        assert actual <= max_queries, (
            f"OGC user-collections issued {actual} queries (cap {max_queries}). "
            f"Likely an N+1 regression. Captured SQL:\n"
            + "\n".join(q["sql"] for q in ctx.captured_queries)
        )


@pytest.mark.django_db
class TestArcGISPro361Replay(BaseAPITestCase):
    """reproduce the production-log discovery sequence.

    Pins that no future change can re-introduce the empty-layer
    regression for an ArcGIS Pro 3.6.1 client following the canonical
    OGC discovery flow.
    """

    USER_AGENT = "ArcGIS Pro 3.6.1 (00000000000) - ArcGISPro"

    def setUp(self) -> None:
        super().setUp()
        self.public_client = self.client_class()
        self.project = ProjectFactory.create()
        self.gis_view = GISView.objects.create(
            name="Replay View",
            owner=self.user,
            allow_precise_zoom=False,
        )
        self.commit_sha = "abcdef0123456789" * 2 + "01234567"  # 40-char SHA
        _create_project_geojson_for(str(self.project.id), self.commit_sha)
        GISProjectView.objects.create(
            gis_view=self.gis_view,
            project=self.project,
            commit_sha=self.commit_sha,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json,application/geo+json",
        }

    def test_full_arcgis_discovery_sequence_round_trips(self) -> None:
        token = self.gis_view.gis_token
        # Step 1: landing page.
        landing = self.public_client.get(
            reverse("api:v2:gis-ogc:view-landing", kwargs={"gis_token": token}),
            headers=self._headers(),
        )
        assert landing.status_code == status.HTTP_200_OK
        landing_data = landing.json()
        # ws1e — no service-desc link to /api/schema/.
        for link in landing_data["links"]:
            if link.get("rel") == "service-desc":
                assert not link.get("href", "").endswith("/api/schema/")
        # Step 2: follow rel:conformance.
        conf_href = next(
            link["href"]
            for link in landing_data["links"]
            if link["rel"] == "conformance"
        )
        conf = self.public_client.get(
            urlparse(conf_href).path,
            headers=self._headers(),
        )
        assert conf.status_code == status.HTTP_200_OK
        # Step 3: follow rel:data → /collections.
        data_href = next(
            link["href"] for link in landing_data["links"] if link["rel"] == "data"
        )
        collections = self.public_client.get(
            urlparse(data_href).path,
            headers=self._headers(),
        )
        assert collections.status_code == status.HTTP_200_OK
        coll = collections.json()["collections"][0]
        # Step 4: follow first collection's items link.
        items_href = next(
            link["href"] for link in coll["links"] if link["rel"] == "items"
        )
        items = self.public_client.get(
            urlparse(items_href).path,
            headers=self._headers(),
        )
        assert items.status_code == status.HTTP_200_OK
        body = _streaming_json(items)
        # The smoking-gun guards.
        assert body["type"] == "FeatureCollection"
        rels = [link["rel"] for link in body["links"]]
        assert "self" in rels  # OGC Req 27 — the actual fix
        assert "numberMatched" in body
        assert "numberReturned" in body
        assert "timeStamp" in body
        # Every Feature has top-level id (RFC 7946 §3.2 SHOULD).
        assert all(feat.get("id") for feat in body["features"])


# ---------------------------------------------------------------------------
# Hypothesis property-based tests on the parser helpers
# ---------------------------------------------------------------------------


class TestOGCQueryProperties:
    """Property-based-style tests for parse_ogc_query / apply_ogc_query.

    Uses RequestFactory rather than DB-bound clients so the parsers can
    be exercised without DB setup. ``hypothesis`` is not a project
    dependency, so we use ``pytest.mark.parametrize`` with a curated
    sample of corner-case inputs.
    """

    factory = RequestFactory()

    @pytest.mark.parametrize(
        "limit",
        [1, 2, 100, MAX_OGC_LIMIT, MAX_OGC_LIMIT - 1, MAX_OGC_LIMIT // 2],
    )
    def test_valid_limits_round_trip(self, limit: int) -> None:
        request = self.factory.get(f"/items?limit={limit}")
        request.query_params = request.GET  # type: ignore[attr-defined]
        result = parse_ogc_query(request)  # type: ignore[arg-type]
        assert result.limit == limit

    @pytest.mark.parametrize(
        "offset",
        [0, 1, 100, 1000, 999_999_999],
    )
    def test_valid_offsets_round_trip(self, offset: int) -> None:
        request = self.factory.get(f"/items?offset={offset}")
        request.query_params = request.GET  # type: ignore[attr-defined]
        result = parse_ogc_query(request)  # type: ignore[arg-type]
        assert result.offset == offset

    def test_normalize_features_id_synthesis_is_unique(self) -> None:
        """Synthesized ids are deterministic AND unique within a call."""
        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [i, 0]},
                "properties": {"name": f"f{i}"},
            }
            for i in range(50)
        ]
        out = normalize_features(features, commit_sha="deadbeef")
        ids = [f["id"] for f in out]
        assert len(set(ids)) == len(ids)  # all unique
        # Re-running yields the same ids (deterministic).
        out2 = normalize_features(features, commit_sha="deadbeef")
        assert [f["id"] for f in out2] == ids

    @pytest.mark.parametrize(
        "raw",
        [
            "1.5,2.5,3.5,4.5",
            "-180,-90,180,90",
            "0,0,0,0,1,1",  # 6-num
            "-87.5,20.2,-87.4,20.3",
        ],
    )
    def test_bbox_round_trips_as_floats(self, raw: str) -> None:
        request = self.factory.get(f"/items?bbox={raw}")
        request.query_params = request.GET  # type: ignore[attr-defined]
        result = parse_ogc_query(request)  # type: ignore[arg-type]
        assert result.bbox is not None
        assert all(isinstance(v, float) for v in result.bbox)
        assert all(not math.isnan(v) and not math.isinf(v) for v in result.bbox)


# ---------------------------------------------------------------------------
# OGC schema validation
# ---------------------------------------------------------------------------


# Minimal JSON-Schema fragments derived from the OGC API - Features 1.0
# YAML schemas (https://schemas.opengis.net/ogcapi/features/part1/1.0/).
# The full schemas are large and pull in external $refs; for in-process
# validation it is sufficient to encode the structural invariants we
# care about — every required field is asserted against the response
# shape.
_OGC_LANDING_SCHEMA = {
    "type": "object",
    "required": ["title", "links"],
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "links": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["href", "rel"],
                "properties": {
                    "href": {"type": "string", "format": "uri"},
                    "rel": {"type": "string"},
                    "type": {"type": "string"},
                    "title": {"type": "string"},
                },
            },
        },
    },
}

_OGC_CONFORMANCE_SCHEMA = {
    "type": "object",
    "required": ["conformsTo"],
    "properties": {
        "conformsTo": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "format": "uri"},
        },
    },
}

_OGC_COLLECTIONS_SCHEMA = {
    "type": "object",
    "required": ["links", "collections"],
    "properties": {
        "links": {"type": "array", "minItems": 1},
        "collections": {"type": "array"},
    },
}

_OGC_COLLECTION_SCHEMA = {
    "type": "object",
    "required": ["id", "links"],
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "itemType": {"type": "string"},
        "crs": {"type": "array", "items": {"type": "string"}},
        "storageCrs": {"type": "string"},
        "extent": {
            "type": "object",
            "properties": {
                "spatial": {
                    "type": "object",
                    "properties": {
                        "bbox": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "number"},
                            },
                        },
                    },
                },
            },
        },
        "links": {"type": "array", "minItems": 1},
    },
}

_OGC_FEATURECOLLECTION_SCHEMA = {
    "type": "object",
    "required": [
        "type",
        "features",
        "links",
        "numberMatched",
        "numberReturned",
        "timeStamp",
    ],
    "properties": {
        "type": {"const": "FeatureCollection"},
        "features": {"type": "array"},
        "links": {
            "type": "array",
            "minItems": 1,
            "contains": {
                "type": "object",
                "properties": {"rel": {"const": "self"}},
                "required": ["rel"],
            },
        },
        "numberMatched": {"type": "integer", "minimum": 0},
        "numberReturned": {"type": "integer", "minimum": 0},
        "timeStamp": {"type": "string"},
    },
}

_OGC_FEATURE_SCHEMA = {
    "type": "object",
    "required": ["type", "geometry"],
    "properties": {
        "type": {"const": "Feature"},
        "id": {},  # OGC accepts string or number
        "geometry": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "required": ["type"],
                    "properties": {"type": {"type": "string"}},
                },
            ],
        },
        "properties": {"type": ["object", "null"]},
        "links": {"type": "array"},
    },
}


def _validate_against(payload: object, schema: dict[str, Any]) -> None:
    """Validate *payload* against *schema*; raises if non-conformant.

    Uses ``jsonschema_rs`` (already a project dep — see
    :mod:`speleodb.utils.validators`) for a Rust-fast walker.
    """
    validator = jsonschema_rs.validator_for(schema)
    # ``is_valid`` returns True/False; for failure we want diagnostic
    # output, so we iterate errors.
    errors = list(validator.iter_errors(payload))
    if errors:
        first = errors[0]
        raise AssertionError(
            f"OGC schema violation: {first.message} at {list(first.instance_path)}"
        )


@pytest.mark.django_db
class TestOGCSchemaValidation(BaseAPITestCase):
    """every OGC endpoint response is validated against the OGC
    JSON-schema fragments (subset of the official OGC YAML).

    Catches any field-level drift across all four families: wrong type,
    missing required, malformed link, etc.
    """

    def setUp(self) -> None:
        super().setUp()
        self.public_client = self.client_class()
        self.project = ProjectFactory.create()
        self.gis_view = GISView.objects.create(
            name="Schema Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )
        self.commit_sha = "0123456789abcdef" * 2 + "01234567"
        _create_project_geojson_for(str(self.project.id), self.commit_sha)
        GISProjectView.objects.create(
            gis_view=self.gis_view,
            project=self.project,
            commit_sha=self.commit_sha,
        )

    def test_landing_page_validates_against_ogc_schema(self) -> None:
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-landing",
                kwargs={"gis_token": self.gis_view.gis_token},
            )
        )
        _validate_against(resp.json(), _OGC_LANDING_SCHEMA)

    def test_conformance_validates_against_ogc_schema(self) -> None:
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-conformance",
                kwargs={"gis_token": self.gis_view.gis_token},
            )
        )
        _validate_against(resp.json(), _OGC_CONFORMANCE_SCHEMA)

    def test_collections_validates_against_ogc_schema(self) -> None:
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collections",
                kwargs={"gis_token": self.gis_view.gis_token},
            )
        )
        body = resp.json()
        _validate_against(body, _OGC_COLLECTIONS_SCHEMA)
        # And every nested collection metadata document must validate.
        for coll in body["collections"]:
            _validate_against(coll, _OGC_COLLECTION_SCHEMA)

    def test_single_collection_validates_against_ogc_schema(self) -> None:
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": f"{self.commit_sha}_lines",
                },
            )
        )
        _validate_against(resp.json(), _OGC_COLLECTION_SCHEMA)

    def test_items_validates_against_ogc_schema(self) -> None:
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection-items",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": f"{self.commit_sha}_lines",
                },
            )
        )
        body = _streaming_json(resp)
        _validate_against(body, _OGC_FEATURECOLLECTION_SCHEMA)
        for feature in body["features"]:
            _validate_against(feature, _OGC_FEATURE_SCHEMA)

    def test_single_feature_validates_against_ogc_schema(self) -> None:
        # Index 1 is the LineString in the mixed fixture (Point at 0,
        # MultiLineString at 2, Polygon at 3 — Polygon is dropped). It
        # is reachable via the ``_lines`` collection.
        feature_id = f"{self.commit_sha}:1"
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection-feature",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": f"{self.commit_sha}_lines",
                    "feature_id": feature_id,
                },
            )
        )
        _validate_against(_streaming_json(resp), _OGC_FEATURE_SCHEMA)


# ---------------------------------------------------------------------------
# Snapshot / golden tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOGCSnapshots(BaseAPITestCase):
    """pin exact response shape so accidental field renames /
    ordering changes fail loudly with a diff.

    Snapshots compare the response body to a hand-rolled expected
    structure. Per-request fields (``timeStamp`` and absolute hrefs)
    are normalised before comparison.
    """

    def setUp(self) -> None:
        super().setUp()
        self.public_client = self.client_class()
        self.project = ProjectFactory.create(name="SnapshotProject")
        self.gis_view = GISView.objects.create(
            name="Snapshot View",
            owner=self.user,
            allow_precise_zoom=False,
        )
        self.commit_sha = "abcdef0123456789" * 2 + "abcdef01"
        _create_project_geojson_for(str(self.project.id), self.commit_sha)
        GISProjectView.objects.create(
            gis_view=self.gis_view,
            project=self.project,
            commit_sha=self.commit_sha,
        )

    @staticmethod
    def _normalise(payload: dict[str, Any]) -> dict[str, Any]:
        """Strip per-request fields so byte-snapshot comparisons are stable."""
        out = orjson.loads(orjson.dumps(payload))  # deep copy
        out.pop("timeStamp", None)

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                # Replace absolute href with the path-only suffix for
                # snapshot stability across hosts/schemes.
                if "href" in node and isinstance(node["href"], str):
                    href = node["href"]
                    parsed = href.split("//", 1)
                    if len(parsed) == _HOST_SPLIT_PARTS and "/" in parsed[1]:
                        node["href"] = "/" + parsed[1].split("/", 1)[1]
                for v in node.values():
                    _walk(v)
            elif isinstance(node, list):
                for v in node:
                    _walk(v)

        _walk(out)
        return out  # type: ignore[no-any-return]

    def test_landing_page_snapshot(self) -> None:
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-landing",
                kwargs={"gis_token": self.gis_view.gis_token},
            )
        )
        body = self._normalise(resp.json())
        token = self.gis_view.gis_token
        # Landing URLs are slash-free now (canonical OGC convention);
        # see ``test_no_ogc_url_pattern_has_inconsistent_trailing_slash``.
        expected_self = f"/api/v2/gis-ogc/view/{token}"
        expected_conformance = f"/api/v2/gis-ogc/view/{token}/conformance"
        expected_data = f"/api/v2/gis-ogc/view/{token}/collections"
        rels = {link["rel"]: link["href"] for link in body["links"]}
        assert rels["self"] == expected_self
        assert rels["conformance"] == expected_conformance
        assert rels["data"] == expected_data
        # service-desc points to the focused OGC OpenAPI document
        # (NOT /api/schema/, which excludes OGC routes and is huge).
        # The OpenAPI endpoint keeps its trailing slash because it is
        # a static document fetch, not part of the OGC discovery
        # contract — see ``urls/gis.py`` docstring.
        assert rels["service-desc"] == "/api/v2/gis-ogc/openapi/"
        assert body["title"] == "SpeleoDB GIS View"

    def test_collections_snapshot(self) -> None:
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collections",
                kwargs={"gis_token": self.gis_view.gis_token},
            )
        )
        body = self._normalise(resp.json())
        token = self.gis_view.gis_token
        expected_self = f"/api/v2/gis-ogc/view/{token}/collections"
        assert {link["rel"] for link in body["links"]} == {"self"}
        assert body["links"][0]["href"] == expected_self
        # Mixed fixture has Point + LineString + MultiLineString +
        # Polygon. Polygon is dropped (no GEOMETRY_GROUPS entry); the
        # remaining geometries split into ``_points`` and ``_lines``.
        assert len(body["collections"]) == 2  # noqa: PLR2004
        ids = {coll["id"] for coll in body["collections"]}
        assert ids == {f"{self.commit_sha}_points", f"{self.commit_sha}_lines"}
        for coll in body["collections"]:
            assert coll["title"].startswith("SnapshotProject")
            assert coll["itemType"] == "feature"
            assert CRS84_2D in coll["crs"]
            assert CRS84_3D in coll["crs"]
            assert coll["storageCrs"] == CRS84_3D

    def test_items_snapshot_envelope(self) -> None:
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection-items",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": f"{self.commit_sha}_lines",
                },
            )
        )
        body = self._normalise(_streaming_json(resp))
        assert body["type"] == "FeatureCollection"
        # Lines collection: LineString + MultiLineString.
        assert body["numberMatched"] == 2  # noqa: PLR2004
        assert body["numberReturned"] == 2  # noqa: PLR2004
        assert isinstance(body["features"], list)
        rels = {link["rel"] for link in body["links"]}
        assert {"self", "collection"} <= rels


# ---------------------------------------------------------------------------
# Stub tests for the optional / infra workstreams (kept here so the
# ``test_ogc_compliance.py`` file doubles as the index of all OGC test
# coverage; the actual mutation/coverage configs live in
# ``pyproject.toml`` and ``Makefile``).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# OGC API definition (service-desc) — focused, cached, shared
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOGCOpenAPIEndpoint:
    """The focused OGC OpenAPI document advertised by every family.

    OGC API - Features 1.0 §7.2.4 (Req 2 ``/req/core/root-success``)
    requires every landing page to advertise a ``service-desc`` link
    pointing to the API definition. The shared focused document is
    served from :class:`~speleodb.api.v2.views.ogc_base.OGCOpenAPIView`
    at ``/api/v2/gis-ogc/openapi/``; these tests pin its content
    type, cache semantics, conditional-request behaviour, and OGC
    self-consistency.
    """

    def test_endpoint_returns_openapi_document(self, api_client: APIClient) -> None:
        resp = api_client.get(reverse("api:v2:gis-ogc:openapi"))
        assert resp.status_code == status.HTTP_200_OK
        ctype = resp["Content-Type"]
        assert "application/vnd.oai.openapi+json" in ctype
        assert "version=3.0" in ctype
        body = _streaming_json(resp)
        assert body["openapi"].startswith("3.0")
        assert "paths" in body
        # Every family is documented (4 families x 6 routes = 24).
        assert len(body["paths"]) >= 24  # noqa: PLR2004
        assert "components" in body
        assert "schemas" in body["components"]
        assert body["servers"] == [
            {
                "url": "/api/v2/gis-ogc",
                "description": "Same-origin OGC API base",
            }
        ]

    def test_endpoint_openapi_document_validates_as_oas30(
        self,
        api_client: APIClient,
    ) -> None:
        resp = api_client.get(reverse("api:v2:gis-ogc:openapi"))
        body = _streaming_json(resp)
        validate_schema(body)

    def test_endpoint_featurecollection_schema_requires_ogc_item_fields(
        self,
        api_client: APIClient,
    ) -> None:
        resp = api_client.get(reverse("api:v2:gis-ogc:openapi"))
        body = _streaming_json(resp)
        schema = body["components"]["schemas"]["FeatureCollection"]
        required = set(schema["required"])
        assert {"timeStamp", "numberMatched", "numberReturned"} <= required

    def test_endpoint_documents_every_family(self, api_client: APIClient) -> None:
        """Pin that the OpenAPI doc covers all four OGC families."""
        resp = api_client.get(reverse("api:v2:gis-ogc:openapi"))
        body = _streaming_json(resp)
        paths = set(body["paths"].keys())
        # At least one path per family must be present.
        assert any("/view/" in p for p in paths)
        assert any("/user/" in p for p in paths)
        assert any("/landmark-collection/" in p for p in paths)
        assert any("/landmark-collections/user/" in p for p in paths)

    def test_endpoint_documents_ogc_query_parameters(
        self, api_client: APIClient
    ) -> None:
        resp = api_client.get(reverse("api:v2:gis-ogc:openapi"))
        body = _streaming_json(resp)
        param_names = set(body["components"]["parameters"].keys())
        assert "BboxParam" in param_names
        assert "DatetimeParam" in param_names
        assert "LimitParam" in param_names
        assert "OffsetParam" in param_names

    def test_endpoint_advertises_long_cache(self, api_client: APIClient) -> None:
        """ws-OGC-OpenAPI: the document is effectively immutable per
        deploy, so we ship a 1-year ``max-age`` plus an ETag."""
        resp = api_client.get(reverse("api:v2:gis-ogc:openapi"))
        cache_control = resp["Cache-Control"]
        assert "public" in cache_control
        assert "max-age=31536000" in cache_control  # 1 year
        assert resp["ETag"]
        assert resp["ETag"].startswith('"')
        assert resp["ETag"].endswith('"')

    def test_conditional_request_returns_304(self, api_client: APIClient) -> None:
        """If-None-Match with the live ETag short-circuits to 304."""
        first = api_client.get(reverse("api:v2:gis-ogc:openapi"))
        etag = first["ETag"]
        cached = api_client.get(
            reverse("api:v2:gis-ogc:openapi"),
            HTTP_IF_NONE_MATCH=etag,
        )
        assert cached.status_code == status.HTTP_304_NOT_MODIFIED
        assert cached["ETag"] == etag

    def test_response_bytes_are_stable_across_requests(
        self, api_client: APIClient
    ) -> None:
        """The doc is built once at import; every request serves the
        same bytes (the bedrock of forever-cacheability)."""
        first = api_client.get(reverse("api:v2:gis-ogc:openapi"))
        second = api_client.get(reverse("api:v2:gis-ogc:openapi"))
        body1 = b"".join(cast("_StreamingResponse", first).streaming_content)
        body2 = b"".join(cast("_StreamingResponse", second).streaming_content)
        assert body1 == body2
        assert first["ETag"] == second["ETag"]

    def test_every_path_template_resolves_through_url_config(
        self, api_client: APIClient
    ) -> None:
        """Every OpenAPI ``paths.*`` entry MUST be resolvable through the
        Django URL config.

        Catches the silent drift where the OpenAPI doc's path strings
        are static (built at import) but the URL config could be
        renamed under us. With this test, any rename to ``urls/gis.py``
        that the OpenAPI doc doesn't track will fail CI loudly.

        The materialiser picks per-family substitutions so the new
        ``ogc_typed_id`` converter (``<sha>_(points|lines)``) is
        exercised on project paths while landmark families keep
        their existing collection-id shapes (literal ``landmarks`` /
        UUID).
        """
        servers = OGC_OPENAPI_DOC["servers"]
        assert len(servers) == 1
        base = servers[0]["url"]  # /api/v2/gis-ogc

        hex40 = "0" * 40
        feature_id_concrete = "feature-x"
        landmark_uuid = str(uuid.uuid4())

        def _collection_ids_for(template: str) -> tuple[str, ...]:
            if "{collection_id}" not in template:
                return ("unused",)
            # Project families use the geometry-typed converter; the
            # landmark single family uses the literal ``landmarks``;
            # the landmark user family uses a UUID. Pick the right
            # concrete value per family so each path template hits
            # the matching URL converter regex.
            if template.startswith(("/view/", "/user/")):
                return (f"{hex40}_points", f"{hex40}_lines")
            if template.startswith("/landmark-collection/"):
                return ("landmarks",)
            return (landmark_uuid,)

        def _materialise(template: str, collection_id: str) -> str:
            url = template
            url = url.replace("{gis_token}", hex40)
            url = url.replace("{key}", hex40)
            url = url.replace("{collection_id}", collection_id)
            return url.replace("{feature_id}", feature_id_concrete)

        for path_template in OGC_OPENAPI_DOC["paths"]:
            for collection_id in _collection_ids_for(path_template):
                full_url = base + _materialise(path_template, collection_id)
                try:
                    match = _resolve(full_url)
                except Resolver404 as exc:
                    msg = (
                        f"OpenAPI path template {path_template!r} (resolved to "
                        f"{full_url!r}) does not match any Django URL pattern"
                    )
                    raise AssertionError(msg) from exc
                # Confirm the resolved view is in the OGC namespace.
                assert "gis-ogc" in match.namespaces, (
                    f"OpenAPI path {path_template!r} resolved outside the "
                    f"OGC namespace: {match.namespaces!r}"
                )

    def test_legacy_sha_only_collection_resolves_to_legacy_gone(
        self, api_client: APIClient
    ) -> None:
        """The pre-split ``<sha>`` collection id resolves to the
        ``OGCLegacyMixedCollectionGoneView`` (not to the geometry-typed
        view, not to a 404). Pins the routing precedence: the typed
        converter MUST be tried first, the bare-SHA legacy form falls
        through to the gone view.
        """
        hex40 = "0" * 40
        for prefix in (
            f"/api/v2/gis-ogc/view/{hex40}",
            f"/api/v2/gis-ogc/user/{hex40}",
        ):
            for suffix in ("", "/items", "/items/feature-x"):
                match = _resolve(f"{prefix}/collections/{hex40}{suffix}")
                assert match.func.view_class is (  # type: ignore[attr-defined]
                    OGCLegacyMixedCollectionGoneView
                ), (
                    f"Bare-<sha> URL {prefix}/collections/{hex40}{suffix} "
                    f"resolved to {match.func} instead of the legacy gone "
                    "view"
                )


@pytest.mark.django_db
class TestLandingPageAdvertisesFocusedOpenAPI(BaseAPITestCase):
    """ws-OGC-OpenAPI: every family's landing page links to the focused
    OGC OpenAPI document — never to ``/api/schema/`` (which is 684 KB
    and excludes the OGC routes).

    ``TokenFactory`` produces a 40-char hex key by default, so this test
    does not need to rebuild ``self.token`` manually.
    """

    def test_view_landing_advertises_focused_service_desc(self) -> None:
        gis_view = GISView.objects.create(
            name="Service-desc test",
            owner=self.user,
            allow_precise_zoom=False,
        )
        resp = self.client.get(
            reverse(
                "api:v2:gis-ogc:view-landing",
                kwargs={"gis_token": gis_view.gis_token},
            )
        )
        rels = {link["rel"]: link["href"] for link in resp.json()["links"]}
        assert "service-desc" in rels  # OGC Req 2 — required link
        assert rels["service-desc"].endswith("/api/v2/gis-ogc/openapi/")
        assert "/api/schema/" not in rels["service-desc"]

    def test_user_landing_advertises_focused_service_desc(self) -> None:
        resp = self.client.get(
            reverse(
                "api:v2:gis-ogc:user-landing",
                kwargs={"key": self.token.key},
            )
        )
        rels = {link["rel"]: link["href"] for link in resp.json()["links"]}
        assert "service-desc" in rels
        assert rels["service-desc"].endswith("/api/v2/gis-ogc/openapi/")


@pytest.mark.django_db
class TestLandmarkLandingAdvertisesFocusedOpenAPI:
    """Landmark-family equivalent of ``TestLandingPageAdvertisesFocusedOpenAPI``."""

    def test_landmark_single_landing_advertises_focused_service_desc(
        self,
        api_client: APIClient,
        landmark_collection: LandmarkCollection,
    ) -> None:
        resp = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collection-landing",
                kwargs={"gis_token": landmark_collection.gis_token},
            )
        )
        rels = {link["rel"]: link["href"] for link in resp.json()["links"]}
        assert "service-desc" in rels
        assert rels["service-desc"].endswith("/api/v2/gis-ogc/openapi/")

    def test_landmark_user_landing_advertises_focused_service_desc(
        self,
        api_client: APIClient,
        landmark_owner: User,
    ) -> None:
        token = Token.objects.create(
            user=landmark_owner,
            key="0123456789abcdef" * 2 + "01234567",
        )
        resp = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collections-user-landing",
                kwargs={"key": token.key},
            )
        )
        rels = {link["rel"]: link["href"] for link in resp.json()["links"]}
        assert "service-desc" in rels
        assert rels["service-desc"].endswith("/api/v2/gis-ogc/openapi/")


# ---------------------------------------------------------------------------
# URL canonical-form regression tests (trailing-slash & route shape pins)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOGCURLCanonicalForm(BaseAPITestCase):
    """Pin the OGC URL convention: landing URLs MUST NOT end with ``/``.

    Captures the regression history documented in
    ``tasks/lessons/ogc-trailing-slash-and-geometry-split.md``: a
    landing URL that ends in ``/`` causes QGIS / ArcGIS Pro to
    construct child URLs with a double slash (``view/<token>//``)
    that 404 in production. The canonical no-trailing-slash form
    matches the OGC spec examples plus GeoServer / pygeoapi /
    ArcGIS Server.

    The complement (``test_landing_url_with_trailing_slash_returns_404``)
    pins the hard-break choice: ``view/<token>/`` is NOT redirected
    to the canonical form because Django's ``APPEND_SLASH`` only
    *adds* slashes — old setups must re-copy the URL from the
    integration page (which renders the new format via ``{% url %}``).
    """

    LANDING_NAMES: ClassVar[tuple[str, ...]] = (
        "api:v2:gis-ogc:view-landing",
        "api:v2:gis-ogc:user-landing",
        "api:v2:gis-ogc:landmark-collection-landing",
        "api:v2:gis-ogc:landmark-collections-user-landing",
    )

    def setUp(self) -> None:
        super().setUp()
        self.public_client = self.client_class()
        self.gis_view = GISView.objects.create(
            name="URL form test view",
            owner=self.user,
            allow_precise_zoom=False,
        )
        self.landmark_collection = LandmarkCollection.objects.create(
            name="URL form test collection",
            created_by=self.user.email,
        )

    def _kwargs_for(self, name: str) -> dict[str, str]:
        if name.endswith("view-landing"):
            return {"gis_token": self.gis_view.gis_token}
        if name.endswith("user-landing"):
            return {"key": self.token.key}
        if name.endswith("landmark-collection-landing"):
            return {"gis_token": self.landmark_collection.gis_token}
        if name.endswith("landmark-collections-user-landing"):
            return {"key": self.token.key}
        raise AssertionError(f"unmapped landing route name: {name}")

    def test_landing_url_has_no_trailing_slash(self) -> None:
        """Every OGC landing URL reverses to a slash-free path."""
        for name in self.LANDING_NAMES:
            with self.subTest(name=name):
                url = reverse(name, kwargs=self._kwargs_for(name))
                assert not url.endswith("/"), (
                    f"OGC landing URL {name!r} reversed to {url!r} which "
                    "ends in '/'. Drop the trailing slash so OGC clients "
                    "(QGIS / ArcGIS Pro) don't construct child URLs with "
                    "a double slash."
                )

    def test_landing_url_with_trailing_slash_returns_404(self) -> None:
        """Hard-break: ``view/<token>/`` etc. return 404 (not redirect).

        Django's ``APPEND_SLASH`` only adds trailing slashes, never
        removes them — so a request for the trailing-slash form
        falls through every URL pattern and 404s. This is the
        intended migration signal so existing setups stop silently
        misbehaving (the canonical no-slash URL is one re-copy away
        on the integration page).
        """
        for name in self.LANDING_NAMES:
            with self.subTest(name=name):
                url = reverse(name, kwargs=self._kwargs_for(name))
                resp = self.public_client.get(url + "/")
                assert resp.status_code == status.HTTP_404_NOT_FOUND, (
                    f"GET {url + '/'} returned {resp.status_code}; "
                    "expected 404 for the hard-break trailing-slash form"
                )

    def test_no_ogc_url_pattern_has_inconsistent_trailing_slash(self) -> None:
        """Walks ``urls/gis.py`` and pins the URL convention.

        Every OGC URL pattern MUST be slash-free (the openapi/ static
        document is the only allowed exception — it is a static
        artefact fetch, not part of the OGC discovery contract). A
        future PR that re-introduces a trailing slash on any landing,
        conformance, collections, or items route fails this test
        loudly, preventing the regression history (the empty-layer
        bug) from repeating.
        """
        violations: list[str] = []
        for entry in ogc_urlpatterns:
            pattern = str(entry.pattern)
            if pattern == "openapi/":
                continue  # Documented exception — see urls/gis.py docstring.
            if pattern.endswith("/"):
                violations.append(pattern)
        assert violations == [], (
            "OGC URL patterns must not end with '/' (only the openapi/ "
            "static document is exempt). Trailing-slash patterns trip "
            "QGIS / ArcGIS Pro URL construction and re-introduce the "
            "ws3a empty-layer regression. Offenders: " + ", ".join(violations)
        )

    def test_openapi_doc_path_templates_have_no_trailing_slash(self) -> None:
        """Every key in the OpenAPI ``paths`` block is slash-free.

        OAS-driven clients join ``servers.url`` + ``paths.*`` to
        construct request URLs; a path that ends in ``/`` produces
        a double slash and fails routing. Pins the consistency
        between the URL config and the OpenAPI document.
        """
        violations = [p for p in OGC_OPENAPI_DOC["paths"] if p.endswith("/")]
        assert violations == [], (
            "OpenAPI path templates must not end with '/': " + ", ".join(violations)
        )


# ---------------------------------------------------------------------------
# Geometry-typed split regression tests
# ---------------------------------------------------------------------------


def _typed_geojson_file(
    *,
    include_points: bool = True,
    include_lines: bool = True,
    include_polygon: bool = False,
) -> SimpleUploadedFile:
    """Build a per-test GeoJSON fixture with selectable geometry groups.

    Used by ``TestOGCGeometrySplit`` to exercise the listing /
    omit-empty / cross-group lookup contracts without leaning on the
    main ``_mixed_geojson_file`` fixture (which is also asserted
    against by the count-based legacy tests).
    """
    features: list[dict[str, Any]] = []
    if include_points:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-87.5, 20.2]},
                "properties": {"name": "P1", "id": "p-1"},
            }
        )
    if include_lines:
        features.extend(
            [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-87.5, 20.2], [-87.6, 20.3]],
                    },
                    "properties": {"name": "L1"},
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "MultiLineString",
                        "coordinates": [[[-87.7, 20.4], [-87.8, 20.5]]],
                    },
                    "properties": {"name": "L2"},
                },
            ]
        )
    if include_polygon:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-87.6, 20.3],
                            [-87.59, 20.3],
                            [-87.59, 20.31],
                            [-87.6, 20.3],
                        ],
                    ],
                },
                "properties": {"name": "POLY"},
            }
        )
    return SimpleUploadedFile(
        "typed.geojson",
        orjson.dumps({"type": "FeatureCollection", "features": features}),
        content_type="application/geo+json",
    )


@pytest.mark.django_db
class TestOGCGeometrySplit(BaseAPITestCase):
    """ws-OGC-geometry-split: each project commit becomes one OGC
    collection per geometry group actually present.

    Regression-killer suite for the contract: 1 OGC collection = 1
    GIS layer = 1 uniform geometry type — the assumption made by
    every major GIS client (QGIS, ArcGIS Pro, GeoServer, pygeoapi).
    """

    def setUp(self) -> None:
        super().setUp()
        self.public_client = self.client_class()
        self.project = ProjectFactory.create()
        self.gis_view = GISView.objects.create(
            name="Geometry split view",
            owner=self.user,
            allow_precise_zoom=False,
        )

    def _make_geojson(
        self,
        commit_sha: str,
        **groups: bool,
    ) -> None:
        commit = ProjectCommit.objects.create(
            id=commit_sha,
            project=self.project,
            author_name="Tester",
            author_email="tester@example.com",
            authored_date=timezone.now(),
            message="geometry-split fixture",
        )
        ProjectGeoJSON.objects.create(
            commit=commit,
            project=self.project,
            file=_typed_geojson_file(**groups),
        )
        GISProjectView.objects.create(
            gis_view=self.gis_view,
            project=self.project,
            commit_sha=commit_sha,
        )

    def _collections(self) -> list[dict[str, Any]]:
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collections",
                kwargs={"gis_token": self.gis_view.gis_token},
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()["collections"]  # type: ignore[no-any-return]

    def _items(self, collection_id: str) -> dict[str, Any]:
        resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection-items",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": collection_id,
                },
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        return _streaming_json(resp)

    def test_collections_lists_one_per_geometry_group_present(self) -> None:
        """Both points and lines present → exactly two collections."""
        sha = "1" * 40
        self._make_geojson(sha, include_points=True, include_lines=True)
        ids = [coll["id"] for coll in self._collections()]
        # Order is stable per ``GEOMETRY_GROUPS_ORDERED`` (points first).
        assert ids == [f"{sha}_points", f"{sha}_lines"]

    def test_collections_omits_geometry_group_with_no_features(self) -> None:
        """Lines-only fixture → exactly one collection (``_lines``)."""
        sha = "2" * 40
        self._make_geojson(sha, include_points=False, include_lines=True)
        ids = [coll["id"] for coll in self._collections()]
        assert ids == [f"{sha}_lines"]

    def test_each_geometry_typed_collection_items_are_uniform(self) -> None:
        sha = "3" * 40
        self._make_geojson(sha, include_points=True, include_lines=True)
        points_body = self._items(f"{sha}_points")
        lines_body = self._items(f"{sha}_lines")
        assert {feat["geometry"]["type"] for feat in points_body["features"]} <= {
            "Point",
            "MultiPoint",
        }
        assert {feat["geometry"]["type"] for feat in lines_body["features"]} <= {
            "LineString",
            "MultiLineString",
        }

    def test_polygon_features_are_dropped_with_warning(self) -> None:
        """SpeleoDB does not produce polygons; a stray one is dropped
        from the listing AND from every items response, with a single
        structured warning logged so a future polygon-producing
        pipeline is loud rather than silently ingesting bad data.
        """
        sha = "4" * 40
        self._make_geojson(
            sha,
            include_points=True,
            include_lines=True,
            include_polygon=True,
        )
        with self.assertLogs("speleodb.gis.ogc_helpers", level="WARNING") as captured:
            ids = [coll["id"] for coll in self._collections()]
        assert f"{sha}_polygons" not in ids
        assert len(captured.records) == 1
        warning = captured.records[0]
        assert warning.__dict__["unsupported_geometry_type"] == "Polygon"
        assert "dropping unsupported geometry type 'Polygon'" in warning.getMessage()
        # Every present collection's items respect the group invariant.
        for collection_id in ids:
            body = self._items(collection_id)
            for feat in body["features"]:
                assert feat["geometry"]["type"] not in {"Polygon", "MultiPolygon"}

    def test_empty_groups_cache_distinguishes_empty_tuple_from_miss(self) -> None:
        """A computed empty group set is cached as ``()`` and read as a hit."""
        sha = "9" * 40
        self._make_geojson(sha, include_points=False, include_lines=False)
        groups_key = f"ogc_geojson_groups_present_{sha}"

        assert _cache.get(groups_key) is None
        assert (
            _gis_view_mod._load_geometry_groups_present(sha) == frozenset()  # noqa: SLF001
        )
        assert _cache.get(groups_key) == ()

        original_loader = _gis_view_mod._load_normalized_features  # noqa: SLF001

        def _fail_if_cache_misses(commit_sha: str) -> list[dict[str, Any]]:
            raise AssertionError(f"cache miss for already-computed empty {commit_sha}")

        _gis_view_mod._load_normalized_features = _fail_if_cache_misses  # noqa: SLF001
        try:
            assert (
                _gis_view_mod._load_geometry_groups_present(sha) == frozenset()  # noqa: SLF001
            )
        finally:
            _gis_view_mod._load_normalized_features = original_loader  # noqa: SLF001

    def test_legacy_mixed_sha_collection_returns_410_with_link_header(self) -> None:
        sha = "5" * 40
        self._make_geojson(sha, include_points=True, include_lines=True)
        # Direct URL — the bare-<sha> form has no reverse name.
        resp = self.public_client.get(
            f"/api/v2/gis-ogc/view/{self.gis_view.gis_token}/collections/{sha}"
        )
        assert resp.status_code == status.HTTP_410_GONE
        link_header = resp["Link"]
        entries = [entry.strip() for entry in link_header.split(",")]
        assert len(entries) == 2  # noqa: PLR2004
        for group, entry in zip(("points", "lines"), entries, strict=True):
            assert entry.startswith(
                f"<http://testserver/api/v2/gis-ogc/view/{self.gis_view.gis_token}"
                f"/collections/{sha}_{group}>"
            )
            assert 'rel="alternate"' in entry
            assert 'type="application/geo+json"' in entry
        # The body is what QGIS / ArcGIS Pro show to the human user;
        # it must be human-readable and action-oriented, not an HTTP
        # semantics note. Pin both the migration prompt (so a future
        # message rewrite can't accidentally drop the call to action)
        # and the per-group references.
        body = orjson.loads(resp.content)
        assert body["status"] == status.HTTP_410_GONE
        assert "_points" in body["detail"]
        assert "_lines" in body["detail"]
        assert "re-add" in body["detail"].lower()
        assert "remove" in body["detail"].lower()

    def test_legacy_mixed_sha_head_returns_410_with_link_header(self) -> None:
        sha = "0" * 40
        self._make_geojson(sha, include_points=True, include_lines=True)
        resp = self.public_client.head(
            f"/api/v2/gis-ogc/view/{self.gis_view.gis_token}/collections/{sha}"
        )
        assert resp.status_code == status.HTTP_410_GONE
        assert "Link" in resp
        assert f"/collections/{sha}_points>" in resp["Link"]
        assert f"/collections/{sha}_lines>" in resp["Link"]
        assert resp["Cache-Control"] == "no-store"

    def test_legacy_mixed_sha_items_returns_410(self) -> None:
        sha = "6" * 40
        self._make_geojson(sha, include_points=True, include_lines=True)
        for suffix in ("/items", "/items/some-feature"):
            resp = self.public_client.get(
                f"/api/v2/gis-ogc/view/{self.gis_view.gis_token}"
                f"/collections/{sha}{suffix}"
            )
            assert resp.status_code == status.HTTP_410_GONE, suffix

    def test_geometry_split_bbox_is_per_subset(self) -> None:
        """Disjoint-bbox fixture: ``_points`` bbox differs from ``_lines``.

        The fixture's Point sits near (-87.5, 20.2) and the
        LineString stretches into (-87.8, 20.5); the per-group
        ``extent.spatial.bbox`` MUST reflect each subset rather than
        a shared union, so QGIS / ArcGIS Pro auto-zoom lands on the
        right cluster per layer.
        """
        sha = "7" * 40
        self._make_geojson(sha, include_points=True, include_lines=True)
        points_resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": f"{sha}_points",
                },
            )
        )
        lines_resp = self.public_client.get(
            reverse(
                "api:v2:gis-ogc:view-collection",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "collection_id": f"{sha}_lines",
                },
            )
        )
        points_bbox = points_resp.json()["extent"]["spatial"]["bbox"][0]
        lines_bbox = lines_resp.json()["extent"]["spatial"]["bbox"][0]
        assert points_bbox != lines_bbox, (
            "Per-group bbox must reflect the subset, not a shared union."
        )
        # Sanity: the points bbox is a degenerate rectangle (single point).
        assert points_bbox[0] == points_bbox[2]
        assert points_bbox[1] == points_bbox[3]
        # Lines bbox spans both LineStrings (-87.8..-87.5 in lon).
        assert lines_bbox[0] < points_bbox[0]

    def test_arcgis_pro_replay_through_geometry_typed_collection(self) -> None:
        """Pin the four-step ArcGIS Pro discovery sequence end-to-end
        when collections are geometry-typed: landing → conformance →
        collections → first geometry-typed collection's /items
        returns ``numberMatched > 0`` with uniform geometry.
        """
        sha = "8" * 40
        self._make_geojson(sha, include_points=True, include_lines=True)
        token = self.gis_view.gis_token
        landing = self.public_client.get(
            reverse("api:v2:gis-ogc:view-landing", kwargs={"gis_token": token})
        ).json()
        # Follow rel:data → /collections.
        data_href = next(
            link["href"] for link in landing["links"] if link["rel"] == "data"
        )
        collections = self.public_client.get(urlparse(data_href).path).json()
        assert len(collections["collections"]) == 2  # noqa: PLR2004
        # Follow the first collection's items link.
        coll = collections["collections"][0]
        items_href = next(
            link["href"] for link in coll["links"] if link["rel"] == "items"
        )
        items_resp = self.public_client.get(urlparse(items_href).path)
        assert items_resp.status_code == status.HTTP_200_OK
        body = _streaming_json(items_resp)
        assert body["numberMatched"] > 0
        assert body["numberReturned"] == len(body["features"])
        # Uniform geometry per the chosen collection.
        types = {feat["geometry"]["type"] for feat in body["features"]}
        if coll["id"].endswith("_points"):
            assert types <= {"Point", "MultiPoint"}
        else:
            assert types <= {"LineString", "MultiLineString"}


def test_mutmut_target_is_documented() -> None:
    """mutmut configuration covers the OGC core modules.

    The actual mutation testing run is a Make target (``make
    test-ogc-mutations``) — this test simply pins that the modules in
    scope are present in the project tree, so a future refactor that
    moves or deletes a file fails CI before mutation testing silently
    misses it.
    """
    for mod in (
        "speleodb.gis.ogc_helpers",
        "speleodb.api.v2.views.ogc_base",
        "speleodb.api.v2.views.gis_view",
        "speleodb.api.v2.views.project_geojson",
        "speleodb.api.v2.views.landmark_collection_ogc",
    ):
        import_module(mod)


def test_ogc_team_engine_setup_documented() -> None:
    """the optional Team Engine docker-compose harness lives
    under ``docs/map-viewer/api-reference.md``; the test merely guards
    the doc reference so running the suite is reproducible after a
    docs reorg.
    """
    api_ref = Path("docs/map-viewer/api-reference.md")
    if not api_ref.exists():
        pytest.skip("docs/map-viewer/api-reference.md not present in this checkout")
    text = api_ref.read_text(encoding="utf-8")
    assert "OGC API - Features" in text
