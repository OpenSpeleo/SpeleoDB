"""Native topology and identity boundaries survive publication into persisted leads."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from contextlib import closing
from datetime import date
from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

import pytest
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
from django.utils import timezone
from openspeleo_core import ariane_core

from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.common.enums import ProjectType
from speleodb.gis.project_geojson_services import replace_project_geojson
from speleodb.surveys.models import ProjectCommit
from speleodb.testing.stalagmight import MAX_SOURCE_BYTES
from speleodb.testing.stalagmight import stalagmight_bytes

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from speleodb.surveys.models.project import GeoJSONBuildResult


@pytest.fixture
def native_commit(request: pytest.FixtureRequest) -> Generator[ProjectCommit]:
    project = ProjectFactory.create(type=request.param, exclude_geojson=False)
    commit = ProjectCommit.objects.create(
        id=uuid4().hex + "0" * 8,
        project=project,
        author_name="Surveyor",
        author_email="surveyor@example.test",
        authored_date=timezone.now(),
        message="Native identity boundary",
    )
    try:
        yield commit
    finally:
        # The fixture owns this database-only project's isolated test-bucket prefix.
        project.purge_geojsons()


def publish(commit: ProjectCommit, path: Path) -> GeoJSONBuildResult:
    assert path.stat().st_size <= MAX_SOURCE_BYTES
    result = commit.project.build_geojson(path)
    replace_project_geojson(
        commit.project, commit, result.geojson, source_shots=result.shots
    )
    return result


@pytest.mark.django_db
@pytest.mark.parametrize("native_commit", [ProjectType.COMPASS], indirect=True)
def test_compass_reversed_duplicates_exclusions_and_native_namespaces(
    native_commit: ProjectCommit, tmp_path: Path
) -> None:
    survey = CompassSurvey(
        header=CompassSurveyHeader(
            cave_name="Native test cave",
            survey_name="Dive",
            date=date(2026, 1, 1),
            has_backsights=False,
        ),
        shots=[
            CompassShot(
                from_station="B",
                to_station="A",
                distance=10,
                frontsight_azimuth=90,
                frontsight_inclination=0,
                comment=comment,
            )
            for comment in ("First !N!", "Second !S!")
        ]
        + [
            CompassShot(
                from_station="A",
                to_station="Hidden",
                distance=10,
                frontsight_azimuth=0,
                frontsight_inclination=0,
                comment="Hidden !E!",
                excluded_from_plotting=True,
            ),
            CompassShot(
                from_station="A",
                to_station="Excluded",
                distance=10,
                frontsight_azimuth=0,
                frontsight_inclination=0,
                comment="Excluded !W!",
                excluded_from_all_processing=True,
            ),
        ],
    )
    directive = FileDirective(
        file="first.dat",
        data=CompassDatFile(surveys=[survey]),
        link_stations=[
            LinkStation(
                name="A",
                location=NEVLocation(
                    easting=500000, northing=4400000, elevation=0, unit="m"
                ),
            )
        ],
    )
    source = CompassMakFile(directives=[UTMZoneDirective(utm_zone=18), directive])
    path = tmp_path / "source.mak"
    save_project(path, source)
    assert (tmp_path / "first.dat").stat().st_size <= MAX_SOURCE_BYTES
    result = publish(native_commit, path)
    project = native_commit.project
    lead = project.exploration_leads.get()
    assert (lead.description, lead.directions) == (
        "First !N!",
        [{"heading": 0, "checked": False}],
    )
    assert [shot.comment for shot in result.shots] == ["First !N!", "Second !S!"]
    assert all(
        (shot.shot_id, shot.from_id, shot.namespace, shot.uuid)
        == ("A", "B", ("first.dat", "Dive"), None)
        for shot in result.shots
    )
    anchor = next(
        feature["geometry"]["coordinates"][:2]
        for feature in result.geojson["features"]
        if feature["geometry"]["type"] == "Point"
    )
    leg = next(
        feature["geometry"]["coordinates"]
        for feature in result.geojson["features"]
        if feature["geometry"]["type"] == "LineString"
    )
    # Rendering traverses outward from anchored A to B. The annotation belongs
    # to the native B-to-A destination A, not the last rendered coordinate.
    assert lead.coordinates == pytest.approx(anchor, abs=1e-6)
    assert lead.coordinates != pytest.approx(leg[-1][:2], abs=1e-7)
    lead.description = "User notes at anchored destination"
    lead.directions = [{"heading": None, "checked": False}]
    lead.save()
    survey.shots.reverse()
    save_project(path, source)
    publish(native_commit, path)
    lead.refresh_from_db()
    assert project.exploration_leads.get().pk == lead.pk
    assert (lead.description, lead.directions) == (
        "User notes at anchored destination",
        [{"heading": None, "checked": False}],
    )

    # With no native UUID, both the DAT path and survey name distinguish sources.
    directive.file = "renamed.dat"
    save_project(path, source)
    publish(native_commit, path)
    expected_lead_count = 2
    assert project.exploration_leads.count() == expected_lead_count
    survey.header.survey_name = "RenamedDive"
    save_project(path, source)
    publish(native_commit, path)
    expected_lead_count += 1
    assert project.exploration_leads.count() == expected_lead_count
    lead.refresh_from_db()
    assert (lead.description, lead.directions) == (
        "User notes at anchored destination",
        [{"heading": None, "checked": False}],
    )


@pytest.mark.django_db
@pytest.mark.parametrize("native_commit", [ProjectType.STALAGMIGHT], indirect=True)
def test_stalagmight_schema_upgrade_retains_live_and_deleted_native_rows(
    native_commit: ProjectCommit, tmp_path: Path
) -> None:
    path = tmp_path / "native.stalx"
    path.write_bytes(stalagmight_bytes())
    with closing(sqlite3.connect(path)) as database, database:
        database.executemany(
            "UPDATE shots SET comment = ? WHERE id = ?",
            [("Hidden jump !E!", 1), ("Live !N!", 2), ("Deleted !S!", 3)],
        )
    initial = publish(native_commit, path)
    project = native_commit.project
    lead = project.exploration_leads.get(description="Live !N!")
    deleted = project.exploration_leads.get(description="Deleted !S!")
    deleted_sources = set(deleted.sources.values_list("pk", flat=True))
    deleted.delete()
    lead.description = "User notes survive schema upgrade"
    lead.directions = [{"heading": None, "checked": False}]
    lead.save()
    saved_values = project.exploration_leads.values().get(pk=lead.pk)
    native_ids = {(shot.shot_id, shot.from_id) for shot in initial.shots}
    assert native_ids == {("2", "1"), ("3", "section:2:root")}

    native_uuids = [str(uuid4()) for _ in range(3)]
    numbers = [71, 103, 223]
    numbering = {
        "next": 224,
        "identities": {
            f"{section}:{native_uuid}": number
            for section, native_uuid, number in zip(
                [1, 1, 2], native_uuids, numbers, strict=True
            )
        },
    }
    graph = {
        "initialized": True,
        "explicit": True,
        "origins": {"71": None, "103": 71, "223": None},
    }
    with closing(sqlite3.connect(path)) as database, database:
        database.executescript(
            "PRAGMA user_version=19; "
            "UPDATE project SET schema_version=19; "
            "CREATE TABLE project_settings(key TEXT, value TEXT);"
        )
        database.executemany(
            "UPDATE shots SET uuid = ? WHERE id = ?",
            [(native_uuid, row) for row, native_uuid in enumerate(native_uuids, 1)],
        )
        database.execute(
            "UPDATE shots SET length = length + 0.1, "
            "azimuth_in = azimuth_in + 0.5, azimuth_out = azimuth_out + 0.5 "
            "WHERE id = 2"
        )
        database.executemany(
            "INSERT INTO project_settings VALUES (?, ?)",
            [
                ("shot_numbering", json.dumps(numbering)),
                ("shot_graph", json.dumps(graph)),
            ],
        )
    upgraded = publish(native_commit, path)
    assert {(shot.shot_id, shot.from_id) for shot in upgraded.shots} == native_ids
    assert {shot.uuid for shot in initial.shots}.isdisjoint(
        shot.uuid for shot in upgraded.shots
    )
    lead.refresh_from_db()
    assert project.exploration_leads.get().pk == lead.pk
    assert project.exploration_leads.values().get(pk=lead.pk) == saved_values
    assert project.exploration_lead_sources.filter(
        pk__in=deleted_sources, lead__isnull=True
    ).count() == len(deleted_sources)
    publish(native_commit, path)
    assert project.exploration_leads.get().pk == lead.pk


@pytest.mark.django_db
@pytest.mark.parametrize("native_commit", [ProjectType.ARIANE], indirect=True)
def test_tml_start_closure_and_excluded_comments_do_not_create_leads(
    native_commit: ProjectCommit, tmp_path: Path
) -> None:
    records: list[dict[str, Any]] = [
        {
            "ID": 50,
            "FromID": -1,
            "Type": "START",
            "Length": 0,
            "Azimut": 0,
            "Latitude": 40,
            "Longitude": -70,
            "Comment": "Start !W!",
        },
        {
            "ID": 75,
            "FromID": 50,
            "Type": "REAL",
            "Length": 10,
            "Azimut": 90,
            "Comment": "Live !N!",
        },
        {
            "ID": 80,
            "FromID": 50,
            "Type": "REAL",
            "Length": 5,
            "Azimut": 0,
            "Excluded": True,
            "Comment": "Excluded !E!",
        },
        {"ID": 90, "FromID": 75, "Type": "REAL", "Length": 10, "Azimut": 270},
        {
            "ID": 100,
            "FromID": 90,
            "Type": "CLOSURE",
            "ClosureToID": 50,
            "Length": 0,
            "Azimut": 0,
            "Comment": "Closure !S!",
        },
    ]
    for record in records:
        record.update(Section="Native loop", Date="2026-01-01", Depth=0)
    xml = ariane_core.dict_to_xml_str(
        {"unit": "m", "Data": {"SurveyData": records}}, root_name="CaveFile"
    )
    assert len(xml.encode()) <= MAX_SOURCE_BYTES
    path = tmp_path / "loop.tml"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Data.xml", xml)
    result = publish(native_commit, path)
    assert {shot.shot_id for shot in result.shots} == {"75", "90"}
    lead = native_commit.project.exploration_leads.get()
    assert (lead.description, lead.directions) == (
        "Live !N!",
        [{"heading": 0, "checked": False}],
    )
    publish(native_commit, path)
    assert native_commit.project.exploration_leads.get().pk == lead.pk
