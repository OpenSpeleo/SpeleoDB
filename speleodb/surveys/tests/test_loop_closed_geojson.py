"""Real source files exercise each application's native loop-closure policy."""

from __future__ import annotations

import datetime as dt
import sqlite3
import zipfile
from contextlib import closing
from typing import TYPE_CHECKING
from typing import Any
from uuid import UUID

import compass_lib.geojson
import compass_lib.interface
import compass_lib.loop_closure.presets
import orjson
import pytest
from compass_lib.constants import FEET_TO_METERS
from compass_lib.io import save_project
from compass_lib.models import NEVLocation
from compass_lib.project.models import CompassMakFile
from compass_lib.project.models import FileDirective
from compass_lib.project.models import LinkStation
from compass_lib.project.models import UTMZoneDirective
from compass_lib.survey.models import CompassDatFile
from compass_lib.survey.models import CompassShot
from compass_lib.survey.models import CompassSurvey
from compass_lib.survey.models import CompassSurveyHeader
from openspeleo_core import ariane_core
from openspeleo_lib.geojson import NoKnownAnchorError
from openspeleo_lib.geojson import survey_to_geojson
from openspeleo_lib.interfaces import ArianeInterface
from openspeleo_lib.interfaces import StalagmightInterface
from openspeleo_lib.loop_closure.presets import (
    InverseLengthWeightedConjugateGradientHorizontalSolver,
)
from openspeleo_lib.loop_closure.presets import (
    LengthAzimuthWeightedLeastSquaresHorizontalSolver,
)

from speleodb.common.enums import ProjectType
from speleodb.surveys.models import Project
from speleodb.testing.stalagmight import MAX_SOURCE_BYTES
from speleodb.testing.stalagmight import stalagmight_bytes
from speleodb.utils.exceptions import GeoJSONGenerationError

if TYPE_CHECKING:
    from pathlib import Path


def _ariane_file(tmp_path: Path, *, invalid: bool = False) -> Path:
    records: list[dict[str, Any]] = [
        {
            "ID": 1,
            "FromID": -1,
            "Type": "START",
            "Length": 0,
            "Depth": 0,
            "Azimut": 0,
            "Latitude": 40.0,
            "Longitude": -70.0,
        },
        {
            "ID": 2,
            "FromID": 1,
            "Type": "REAL",
            "Length": 0.5 if invalid else 5,
            "Depth": 1,
            "Azimut": 90,
        },
        {
            "ID": 3,
            "FromID": 2,
            "Type": "REAL",
            "Length": 15,
            "Depth": 2,
            "Azimut": 270,
        },
        {
            "ID": 4,
            "FromID": 3,
            "ClosureToID": 1,
            "Type": "CLOSURE",
            "Length": 0,
            "Depth": 0,
            "Azimut": 0,
        },
    ]
    for record in records:
        record.update(Section="Synthetic", Date="2026-01-01")
    xml = ariane_core.dict_to_xml_str(
        {"unit": "m", "Data": {"SurveyData": records}}, root_name="CaveFile"
    )
    path = tmp_path / "loop.tml"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Data.xml", xml)
    assert path.stat().st_size <= MAX_SOURCE_BYTES
    return path


def _stalagmight_file(tmp_path: Path) -> Path:
    with closing(sqlite3.connect(":memory:")) as database, database:
        database.deserialize(stalagmight_bytes())
        database.executescript(
            "DELETE FROM station_merges; DELETE FROM shots; "
            "DELETE FROM sections WHERE id = 2; "
            "UPDATE sections SET azimuth_north = 'true', azimuth_correction = 0; "
            "CREATE TABLE loop_closures (id INTEGER, station_a_section INTEGER, "
            "station_a_index INTEGER, station_b_section INTEGER, "
            "station_b_index INTEGER, path_length REAL, misclosure_distance REAL, "
            "error_percentage REAL, horizontal_misclosure REAL, "
            "vertical_misclosure REAL, strategy TEXT, is_aligned INTEGER); "
            "INSERT INTO loop_closures VALUES "
            "(1, 1, 3, 1, 0, 35, 0, 0, NULL, NULL, 'LeastSquaresWeighted', 0);"
        )
        database.executemany(
            "INSERT INTO shots VALUES (?, 1, ?, ?, ?, ?, ?, ?, NULL, NULL, "
            "NULL, NULL, NULL, NULL, NULL, 0, NULL, NULL, ?)",
            [
                (
                    index + 1,
                    index,
                    bearing,
                    bearing,
                    length,
                    depth_in,
                    depth_out,
                    str(UUID(int=index + 1, version=4)),
                )
                for index, (bearing, length, depth_in, depth_out) in enumerate(
                    ((90, 10, 5, 6), (0, 10, 6, 7), (225, 15, 7, 5))
                )
            ],
        )
        database.commit()
        payload = database.serialize()
    assert len(payload) <= MAX_SOURCE_BYTES
    path = tmp_path / "loop.stalx"
    path.write_bytes(payload)
    return path


def _compass_file(tmp_path: Path) -> Path:
    survey = CompassSurvey(
        header=CompassSurveyHeader(
            survey_name="Traverse", date=dt.date(2026, 1, 1), has_backsights=False
        ),
        shots=[
            CompassShot(
                from_station=start,
                to_station=stop,
                distance=length / FEET_TO_METERS,
                frontsight_azimuth=90.0,
                frontsight_inclination=0.0,
            )
            for start, stop, length in (("A", "B", 5.0), ("B", "C", 15.0))
        ],
    )
    project = CompassMakFile(
        directives=[
            UTMZoneDirective(utm_zone=18),
            FileDirective(
                file="loop.dat",
                data=CompassDatFile(surveys=[survey]),
                link_stations=[
                    LinkStation(
                        name="A",
                        location=NEVLocation(
                            easting=500000.0,
                            northing=4400000.0,
                            elevation=0.0,
                            unit="m",
                        ),
                    ),
                    LinkStation(
                        name="C",
                        location=NEVLocation(
                            easting=500024.0,
                            northing=4400000.0,
                            elevation=4.0,
                            unit="m",
                        ),
                    ),
                ],
            ),
        ]
    )
    path = tmp_path / "loop.mak"
    save_project(path, project)
    assert all(p.stat().st_size <= MAX_SOURCE_BYTES for p in tmp_path.iterdir())
    return path


@pytest.mark.parametrize(
    "project_type", [ProjectType.ARIANE, ProjectType.STALAGMIGHT, ProjectType.COMPASS]
)
def test_project_uses_source_format_loop_closure(
    tmp_path: Path, project_type: ProjectType
) -> None:
    match project_type:
        case ProjectType.ARIANE:
            path = _ariane_file(tmp_path)
            source = ArianeInterface.from_file(path)
            expected = survey_to_geojson(
                source,
                loop_closure_solver=(
                    InverseLengthWeightedConjugateGradientHorizontalSolver
                ),
            )
            measured = survey_to_geojson(ArianeInterface.from_file(path))
        case ProjectType.STALAGMIGHT:
            path = _stalagmight_file(tmp_path)
            source = StalagmightInterface.from_file(path)
            expected = survey_to_geojson(
                source,
                loop_closure_solver=LengthAzimuthWeightedLeastSquaresHorizontalSolver,
            )
            measured = survey_to_geojson(StalagmightInterface.from_file(path))
        case ProjectType.COMPASS:
            path = _compass_file(tmp_path)
            model = compass_lib.interface.CompassInterface.load_project(path)
            options: dict[str, Any] = {
                "include_stations": False,
                "include_legs": True,
                "include_passages": False,
                "include_anchors": True,
                "color_by_origin": False,
            }
            expected = compass_lib.geojson.project_to_geojson(
                model,
                **options,
                loop_closure=compass_lib.loop_closure.presets.InverseLengthWeightedL1SpatialSolver,
            )
            measured = compass_lib.geojson.project_to_geojson(model, **options)
        case _:
            raise AssertionError(project_type)
    original = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    actual = Project(type=project_type).build_geojson(path)
    actual, expected, measured = (
        orjson.loads(orjson.dumps(output)) for output in (actual, expected, measured)
    )
    if project_type == ProjectType.COMPASS:
        # Compass randomly assigns section colors on every export, independently
        # of color_by_origin. Compare closure output without that display metadata.
        for output in (actual, expected, measured):
            for feature in output["features"]:
                feature["properties"].pop("color", None)
    assert actual == expected
    assert actual != measured
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == original


def test_single_anchor_stalagmight_closes_without_dropping_depths(
    tmp_path: Path,
) -> None:
    path = _stalagmight_file(tmp_path)
    measured = survey_to_geojson(StalagmightInterface.from_file(path))
    actual = orjson.loads(
        orjson.dumps(Project(type=ProjectType.STALAGMIGHT).build_geojson(path))
    )
    start, *legs = actual["features"]
    assert start["geometry"]["coordinates"] == [-70.0, 40.0]
    assert legs[-1]["geometry"]["coordinates"][-1] == start["geometry"]["coordinates"]
    assert (
        legs[0]["geometry"]["coordinates"][-1]
        != measured["features"][1]["geometry"]["coordinates"][-1]
    )
    assert [f["properties"]["depth"] for f in actual["features"]] == [
        f["properties"]["depth"] for f in measured["features"]
    ]


def test_invalid_source_fails_without_changing_input(tmp_path: Path) -> None:
    path = _ariane_file(tmp_path, invalid=True)
    before = path.read_bytes()
    with pytest.raises(GeoJSONGenerationError):
        Project(type=ProjectType.ARIANE).build_geojson(path)
    assert path.read_bytes() == before


def test_unanchored_stalagmight_remains_an_expected_omission(tmp_path: Path) -> None:
    path = tmp_path / "unanchored.stalx"
    before = stalagmight_bytes(anchored=False)
    path.write_bytes(before)
    with pytest.raises(NoKnownAnchorError):
        Project(type=ProjectType.STALAGMIGHT).build_geojson(path)
    assert path.read_bytes() == before


def test_ariane_closes_target_and_preserves_recorded_depths(tmp_path: Path) -> None:
    path = _ariane_file(tmp_path)
    measured = survey_to_geojson(ArianeInterface.from_file(path))
    actual = orjson.loads(
        orjson.dumps(Project(type=ProjectType.ARIANE).build_geojson(path))
    )
    start, *legs = actual["features"]
    assert start["geometry"]["coordinates"] == [-70.0, 40.0]
    assert legs[-1]["geometry"]["coordinates"][-1] == start["geometry"]["coordinates"]
    assert [feature["properties"]["depth"] for feature in actual["features"]] == [
        feature["properties"]["depth"] for feature in measured["features"]
    ]


def test_compass_l1_retains_short_leg_elevation_and_fixed_controls(
    tmp_path: Path,
) -> None:
    path = _compass_file(tmp_path)
    actual = Project(type=ProjectType.COMPASS).build_geojson(path)
    legs = [
        feature
        for feature in actual["features"]
        if feature["geometry"]["type"] == "LineString"
    ]
    # L1 assigns the vertical discrepancy to the longer leg, rather than
    # spreading it across both legs as the previous Gaussian configuration did.
    assert legs[0]["geometry"]["coordinates"][0][2] == 0.0
    assert legs[0]["geometry"]["coordinates"][-1][2] == 0.0
    expected_anchor_elevation = 4.0
    assert legs[-1]["geometry"]["coordinates"][-1][2] == expected_anchor_elevation
