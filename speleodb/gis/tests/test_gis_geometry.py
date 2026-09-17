"""Geometry validation, atomic persistence, and optimistic edits without GitLab."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError

from speleodb.common.enums import PermissionLevel
from speleodb.gis import geometry_validation
from speleodb.gis.geometry_services import GISGeometryConflictError
from speleodb.gis.geometry_services import create_gis_geometry
from speleodb.gis.geometry_services import update_gis_geometry
from speleodb.gis.geometry_validation import GIS_GEOMETRY_MAX_VERTICES
from speleodb.gis.geometry_validation import inspect_gis_geometry
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISGeometryUserPermission
from speleodb.users.tests.factories import UserFactory

LINE: dict[str, Any] = {
    "type": "LineString",
    "coordinates": [[-87.5, 20.1], [-87.499, 20.1]],
}
UPDATED_REVISION = 2
AREA_CASES: list[dict[str, Any]] = json.loads(
    Path(__file__).with_name("fixtures").joinpath("gis_geometry_cases.json").read_text()
)


@pytest.mark.parametrize("case", AREA_CASES, ids=lambda case: case["id"])
def test_shared_browser_and_server_area_cases(case: dict[str, Any]) -> None:
    if not case["valid"]:
        with pytest.raises(ValidationError):
            inspect_gis_geometry(case["geojson"])
        return
    metrics = inspect_gis_geometry(case["geojson"])
    assert metrics.bbox_area_m2 == pytest.approx(case["area_m2"], abs=0.000001)
    assert metrics.vertex_count == case["vertex_count"]


def test_python_limits_consume_the_same_contract_as_the_browser() -> None:
    contract: dict[str, Any] = json.loads(
        Path(geometry_validation.__file__)
        .with_name("geometry_contract.json")
        .read_text()
    )
    exported: dict[str, Any] = {
        "types": sorted(geometry_validation.GIS_GEOMETRY_TYPES),
        "max_vertices": geometry_validation.GIS_GEOMETRY_MAX_VERTICES,
        "max_area_m2": geometry_validation.GIS_GEOMETRY_MAX_AREA_M2,
        "warning_area_m2": geometry_validation.GIS_GEOMETRY_WARNING_AREA_M2,
        "earth_radius_m": geometry_validation.GIS_GEOMETRY_EARTH_RADIUS_M,
        "name_max_length": geometry_validation.GIS_GEOMETRY_NAME_MAX_LENGTH,
        "position_dimensions": geometry_validation.POSITION_DIMENSIONS,
        "min_line_vertices": geometry_validation.MIN_LINE_VERTICES,
        "min_polygon_vertices": geometry_validation.MIN_POLYGON_VERTICES,
        "longitude_limit": geometry_validation.LONGITUDE_LIMIT,
        "latitude_limit": geometry_validation.LATITUDE_LIMIT,
        "square_metres_per_square_kilometre": (
            geometry_validation.SQUARE_METRES_PER_SQUARE_KILOMETRE
        ),
    }
    assert exported == contract


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {},
        {"type": "Feature", "geometry": LINE, "properties": {}},
        {
            "type": "LineString",
            "coordinates": [[0, 0], [0.01, 0]],
            "bbox": [0, 0, 0, 0],
        },
        {"type": [], "coordinates": [0, 0]},
        {"type": "LineString", "coordinates": [[0, 0], [0, 0, 0]]},
        {"type": "LineString", "coordinates": [[0, 0], [True, 0]]},
        {"type": "LineString", "coordinates": [[0, 0], ["1", 0]]},
        {"type": "LineString", "coordinates": [[0, 0], [math.nan, 0]]},
        {"type": "LineString", "coordinates": [[0, 0], [math.inf, 0]]},
        {"type": "LineString", "coordinates": [[0, 0], [10**1000, 0]]},
        {"type": "LineString", "coordinates": [[0, 0], [181, 0]]},
        {"type": "LineString", "coordinates": [[0, 0], [0, -91]]},
        {"type": "LineString", "coordinates": []},
        {"type": "LineString", "coordinates": [[0, 0]]},
        {"type": "LineString", "coordinates": [[0, 0], [0, 0]]},
        {"type": "LineString", "coordinates": [[179.99, 1], [-179.99, 1]]},
        {"type": "Polygon", "coordinates": []},
        {"type": "Polygon", "coordinates": [[]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [0.01, 0], [0, 0.01]]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [0.01, 0], [0.02, 0], [0, 0]]]},
        {
            "type": "Polygon",
            "coordinates": [[[0, 0], [0.01, 0.01], [0, 0.01], [0.01, 0], [0, 0]]],
        },
        {
            "type": "Polygon",
            "coordinates": [[[0, 0], [0.01, 0], [0, 0.01], [0, 0]], [[0, 0]]],
        },
        {"type": "Point", "coordinates": [0, 0]},
        {"type": "MultiPoint", "coordinates": [[0, 0]]},
    ],
)
def test_invalid_geojson_is_rejected(value: Any) -> None:
    with pytest.raises(ValidationError):
        inspect_gis_geometry(value)


def _polygon(vertex_count: int) -> dict[str, Any]:
    ring: list[list[float]] = [
        [
            math.cos(index * math.tau / vertex_count) * 0.001,
            math.sin(index * math.tau / vertex_count) * 0.001,
        ]
        for index in range(vertex_count)
    ]
    return {"type": "Polygon", "coordinates": [[*ring, ring[0]]]}


def test_one_hundred_vertices_excludes_polygon_closure() -> None:
    geometry: dict[str, Any] = _polygon(GIS_GEOMETRY_MAX_VERTICES)
    assert inspect_gis_geometry(geometry).vertex_count == GIS_GEOMETRY_MAX_VERTICES
    with pytest.raises(ValidationError, match="100 vertices"):
        inspect_gis_geometry(_polygon(GIS_GEOMETRY_MAX_VERTICES + 1))
    line: dict[str, Any] = {
        "type": "LineString",
        "coordinates": [
            [index / 1000, 0] for index in range(GIS_GEOMETRY_MAX_VERTICES)
        ],
    }
    assert inspect_gis_geometry(line).vertex_count == GIS_GEOMETRY_MAX_VERTICES
    line["coordinates"].append([0.1, 0])
    with pytest.raises(ValidationError, match="100 vertices"):
        inspect_gis_geometry(line)


def test_clockwise_and_counterclockwise_polygons_are_accepted() -> None:
    geometry: dict[str, Any] = _polygon(4)
    area: float = inspect_gis_geometry(geometry).bbox_area_m2
    geometry["coordinates"][0].reverse()
    assert inspect_gis_geometry(geometry).bbox_area_m2 == area


@pytest.mark.django_db
def test_creator_admin_and_failed_creation_are_atomic() -> None:
    creator = UserFactory.create()
    geometry = create_gis_geometry(GISGeometry(name="Entrance", geojson=LINE), creator)
    assert geometry.created_by == creator.email
    assert geometry.permissions.get(user=creator).level == PermissionLevel.ADMIN
    assert geometry.revision == 1
    with pytest.raises(ValidationError):
        create_gis_geometry(GISGeometry(name="Invalid", geojson={}), creator)
    assert GISGeometry.objects.count() == 1
    assert GISGeometryUserPermission.objects.count() == 1


@pytest.mark.django_db
def test_update_preserves_revisions_and_rolls_back_invalid_changes() -> None:
    creator = UserFactory.create()
    geometry = create_gis_geometry(GISGeometry(name="Entrance", geojson=LINE), creator)
    updated = update_gis_geometry(
        geometry_id=geometry.id,
        actor=creator,
        expected_revision=1,
        updates={"name": "New entrance"},
    )
    assert updated.revision == UPDATED_REVISION
    with pytest.raises(GISGeometryConflictError):
        update_gis_geometry(
            geometry_id=geometry.id,
            actor=creator,
            expected_revision=1,
            updates={"name": "Stale"},
        )
    with pytest.raises(ValidationError):
        update_gis_geometry(
            geometry_id=geometry.id,
            actor=creator,
            expected_revision=2,
            updates={"name": "Invalid", "geojson": {}},
        )
    geometry.refresh_from_db()
    assert geometry.revision == UPDATED_REVISION
    assert geometry.name == "New entrance"
    assert geometry.geojson == LINE


@pytest.mark.django_db
def test_creator_provenance_does_not_bypass_revoked_permission() -> None:
    creator = UserFactory.create()
    geometry = create_gis_geometry(GISGeometry(name="Entrance", geojson=LINE), creator)
    geometry.permissions.get(user=creator).deactivate(creator)
    with pytest.raises(PermissionDenied):
        update_gis_geometry(
            geometry_id=geometry.id,
            actor=creator,
            expected_revision=1,
            updates={"name": "Blocked"},
        )


@pytest.mark.django_db
def test_soft_delete_retains_shape_and_deactivates_access() -> None:
    creator = UserFactory.create()
    geometry = create_gis_geometry(GISGeometry(name="Entrance", geojson=LINE), creator)
    geometry.deactivate(creator)
    geometry.refresh_from_db()
    permission = geometry.permissions.get(user=creator)
    assert not geometry.is_active
    assert geometry.geojson == LINE
    assert not permission.is_active
    assert permission.deactivated_by == creator
    assert permission.modified_date == geometry.modified_date
