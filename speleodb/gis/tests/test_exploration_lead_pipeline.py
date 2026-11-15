"""Native survey files, immutable Git history, object storage and persisted leads."""

from __future__ import annotations

import sqlite3
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import orjson
import pytest
from compass_lib.interface import CompassInterface
from django.conf import settings
from git import Actor
from openspeleo_core import ariane_core

from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.common.enums import ProjectType
from speleodb.gis.models import ExplorationLeadSource
from speleodb.gis.project_geojson_services import replace_project_geojson
from speleodb.git_engine.core import GitRepo
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.surveys.models.project import ConversionFailedError
from speleodb.surveys.models.project import ResolvedSurveyShot
from speleodb.testing.stalagmight import MAX_SOURCE_BYTES
from speleodb.testing.stalagmight import stalagmight_bytes

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@dataclass
class NativeSurvey:
    project: Project
    repository: GitRepo
    source: Path
    shot_id: str
    other_id: str

    def edit(
        self,
        shot_id: str,
        *,
        comment: str,
        length_delta: float = 0,
        azimuth_delta: float = 0,
        native_uuid: str | None = None,
        renamed_id: str | None = None,
    ) -> None:
        """Edit native bytes, keeping the actual readers/solvers in the test path."""
        match self.project.type:
            case ProjectType.ARIANE:
                data = ariane_core.load_ariane_tml_file_to_dict(self.source)["CaveFile"]
                records = data["Data"]["SurveyData"]
                record = next(row for row in records if str(row["ID"]) == shot_id)
                record["Comment"] = comment
                record["Length"] = float(record["Length"]) + length_delta
                record["Azimut"] = float(record["Azimut"]) + azimuth_delta
                if native_uuid is not None:
                    record["UUID"] = native_uuid
                if renamed_id is not None:
                    record["ID"] = int(renamed_id)
                    for row in records:
                        if str(row["FromID"]) == shot_id:
                            row["FromID"] = int(renamed_id)
                xml = ariane_core.dict_to_xml_str(data, root_name="CaveFile")
                assert len(xml.encode()) <= MAX_SOURCE_BYTES
                with zipfile.ZipFile(self.source, "w") as archive:
                    archive.writestr("Data.xml", xml)
            case ProjectType.COMPASS:
                data_file = self.source.parent / "sample-1.dat"
                survey = CompassInterface.load_dat(data_file)
                shot = next(
                    shot
                    for section in survey.surveys
                    for shot in section.shots
                    if shot.to_station_name == shot_id
                )
                shot.comment = comment
                assert shot.length is not None
                shot.length += length_delta
                assert shot.frontsight_azimuth is not None
                shot.frontsight_azimuth += azimuth_delta
                CompassInterface.save_dat(survey, data_file)
            case ProjectType.STALAGMIGHT:
                with closing(sqlite3.connect(self.source)) as database, database:
                    database.execute(
                        "UPDATE shots SET comment = ?, length = length + ?, "
                        "azimuth_in = azimuth_in + ?, azimuth_out = azimuth_out + ? "
                        "WHERE id = ?",
                        (comment, length_delta, azimuth_delta, azimuth_delta, shot_id),
                    )
                    if native_uuid is not None:
                        database.execute(
                            "UPDATE shots SET uuid = ? WHERE id = ?",
                            (native_uuid, shot_id),
                        )
                    if renamed_id is not None:
                        database.execute(
                            "UPDATE shots SET id = ? WHERE id = ?",
                            (renamed_id, shot_id),
                        )
            case _:
                raise AssertionError(self.project.type)
        assert all(
            path.stat().st_size <= MAX_SOURCE_BYTES
            for path in self.source.parent.iterdir()
            if path.is_file()
        )

    def commit(
        self, message: str, *, authored_at: datetime | None = None
    ) -> ProjectCommit:
        self.repository.git.add(A=True)
        actor = Actor("Native surveyor", "surveyor@example.test")
        self.repository.index.commit(
            message,
            author=actor,
            committer=actor,
            author_date=authored_at,
            commit_date=authored_at,
        )
        return ProjectCommit.get_or_create_from_commit(
            self.project, self.repository.head.commit
        )

    def convert(self, *, force: bool = False, revision: str | None = None) -> None:
        source_bytes = {
            path: path.read_bytes()
            for path in self.source.parent.iterdir()
            if path.is_file()
        }
        head = self.repository.head.commit.hexsha
        self.project.convert_geojson_history(
            self.repository,
            self.source.parent.parent,
            force_recompute=force,
            revision=revision,
        )
        assert self.repository.head.commit.hexsha == head
        assert all(
            path.read_bytes() == payload for path, payload in source_bytes.items()
        )

    def resolved(self, shot_id: str) -> ResolvedSurveyShot:
        return next(
            shot
            for shot in self.project.build_geojson(self.source).shots
            if shot.shot_id == shot_id
        )


@pytest.fixture(params=["tml", "tml-native-uuid", "compass", "stalagmight"])
def native_survey(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Generator[NativeSurvey]:
    artifacts = settings.BASE_DIR / "speleodb/api/v2/tests/artifacts"
    directory = tmp_path / "source"
    match request.param:
        case "tml" | "tml-native-uuid":
            project_type = ProjectType.ARIANE
            filename, shot_id, other_id = "ariane.tml", "1", "2"
            sources = {filename: (artifacts / "test_simple.tml").read_bytes()}
        case "compass":
            project_type = ProjectType.COMPASS
            filename, shot_id, other_id = "sample.mak", "Main3", "Main4"
            sources = {
                name: (artifacts / name).read_bytes()
                for name in (
                    "compass.toml",
                    "sample.mak",
                    "sample-1.dat",
                    "sample-2.dat",
                    "sample.plt",
                )
            }
        case "stalagmight":
            project_type = ProjectType.STALAGMIGHT
            filename, shot_id, other_id = "stalagmight.stalx", "2", "3"
            sources = {filename: stalagmight_bytes()}
        case _:
            raise AssertionError(request.param)
    project = ProjectFactory.create(type=project_type, exclude_geojson=False)
    repository = GitRepo.init(directory)
    with repository:
        for name, payload in sources.items():
            assert len(payload) <= MAX_SOURCE_BYTES
            (directory / name).write_bytes(payload)
        survey = NativeSurvey(
            project, repository, directory / filename, shot_id, other_id
        )
        if request.param == "tml-native-uuid":
            survey.edit(shot_id, comment="", native_uuid=str(uuid4()))
        elif request.param == "tml":
            assert survey.resolved(shot_id).uuid is None
        try:
            yield survey
        finally:
            # This fixture owns only this database-only project's test-bucket prefix.
            # Exercise the real storage backend without provisioning a GitLab remote.
            project.purge_geojsons()


@pytest.mark.django_db
@pytest.mark.parametrize("user_headings", [[], [12.5, 270.0]], ids=["reset", "edited"])
def test_changed_native_shot_preserves_user_edits(
    native_survey: NativeSurvey, user_headings: list[float]
) -> None:
    survey = native_survey
    comment = "decorate black, stag, !s! !down!"
    survey.edit(survey.shot_id, comment=comment)
    survey.edit(survey.other_id, comment="Invalid !ZAW! !399! !360!")
    first = survey.commit("Annotated native source")
    survey.convert()
    lead = survey.project.exploration_leads.get()
    assert (lead.description, lead.headings, lead.created_by) == (
        comment,
        [180],
        first.author_email,
    )
    original = survey.resolved(survey.shot_id)
    original_coordinates = lead.longitude, lead.latitude
    assert (float(lead.longitude), float(lead.latitude)) == pytest.approx(
        (original.longitude, original.latitude), abs=1e-7
    )
    if survey.project.type == ProjectType.COMPASS:
        assert original.uuid is None
    if original.uuid is None:
        assert not survey.project.exploration_lead_sources.filter(
            kind=ExplorationLeadSource.Kind.UUID
        ).exists()
    assert survey.project.exploration_lead_sources.filter(lead=lead).exists()
    lead.description = "User's field notes; keep this exactly"
    lead.headings = user_headings
    lead.longitude += Decimal("0.001")
    lead.latitude += Decimal("0.001")
    lead.save()
    edited_values = survey.project.exploration_leads.values().get(pk=lead.pk)
    source_rows = list(
        survey.project.exploration_lead_sources.values_list("pk", flat=True)
    )
    survey.convert(force=True)
    lead.refresh_from_db()
    assert survey.project.exploration_leads.values().get(pk=lead.pk) == edited_values

    survey.edit(
        survey.shot_id,
        comment="Changed source !N! !E!",
        length_delta=0.1,
        azimuth_delta=0.5,
    )
    later = survey.commit("Slight measurement and comment correction")
    survey.convert()
    moved = survey.resolved(survey.shot_id)
    assert (moved.length_m, moved.azimuth) != (original.length_m, original.azimuth)
    lead.refresh_from_db()
    assert survey.project.exploration_leads.get().pk == lead.pk
    assert (moved.longitude, moved.latitude) != pytest.approx(
        tuple(float(value) for value in original_coordinates), abs=1e-7, rel=0
    )
    assert survey.project.exploration_leads.values().get(pk=lead.pk) == edited_values
    assert survey.project.exploration_lead_sources.filter(
        pk__in=source_rows, lead=lead
    ).count() == len(source_rows)
    with survey.project.geojsons.get(commit=later).file.open("rb") as stored:
        assert orjson.loads(stored.read())["features"]
    survey.convert(force=True, revision=first.pk)
    lead.refresh_from_db()
    assert survey.project.exploration_leads.values().get(pk=lead.pk) == edited_values
    survey.edit(survey.shot_id, comment="Markers removed", length_delta=0.1)
    survey.commit("Remove source annotation")
    survey.convert()
    lead.refresh_from_db()
    assert survey.project.exploration_leads.get().pk == lead.pk
    assert survey.project.exploration_leads.values().get(pk=lead.pk) == edited_values


@pytest.mark.django_db
def test_deleted_native_lead_survives_changed_shot_and_history_rebuild(
    native_survey: NativeSurvey,
) -> None:
    survey = native_survey
    survey.edit(survey.shot_id, comment="Deleted source !NE!")
    survey.commit("Original annotation")
    survey.convert()
    survey.project.exploration_leads.get().delete()
    signatures = set(
        survey.project.exploration_lead_sources.values_list("pk", flat=True)
    )
    survey.edit(
        survey.shot_id,
        comment="Restored marker !S!",
        length_delta=0.1,
        azimuth_delta=0.5,
        native_uuid=str(uuid4()),
    )
    survey.commit("Edited deleted source")
    survey.convert(force=True)
    assert not survey.project.exploration_leads.exists()
    assert not survey.project.exploration_lead_sources.filter(
        lead__isnull=False
    ).exists()
    assert (
        set(survey.project.exploration_lead_sources.values_list("pk", flat=True))
        > signatures
    )
    if survey.project.type != ProjectType.COMPASS:
        # The newly learned UUID must suppress recreation after native IDs change.
        survey.edit(survey.shot_id, comment="Still deleted !W!", renamed_id="99")
        survey.commit("Changed native ID after learning deleted UUID")
        survey.convert()
        assert not survey.project.exploration_leads.exists()
    # Rebuildable metadata and objects are removed; source tombstones must remain.
    survey.project.commits.all().delete()
    survey.project.purge_geojsons()
    survey.project.construct_git_history_from_project(survey.repository)
    survey.convert(force=True)
    assert not survey.project.exploration_leads.exists()
    assert survey.project.exploration_lead_sources.filter(
        pk__in=signatures
    ).count() == len(signatures)


@pytest.mark.django_db
def test_force_recompute_imports_only_latest_native_comments(
    native_survey: NativeSurvey,
) -> None:
    survey = native_survey
    survey.edit(survey.shot_id, comment="Historical only !N!")
    old = survey.commit("Historical annotation")
    result = survey.project.build_geojson(survey.source)
    replace_project_geojson(survey.project, old, result.geojson)
    survey.edit(survey.shot_id, comment="Annotation removed")
    survey.edit(survey.other_id, comment="decorate black, stag, !s! !down!")
    latest = survey.commit("Current annotation")
    result = survey.project.build_geojson(survey.source)
    replace_project_geojson(survey.project, latest, result.geojson)
    survey.convert()
    assert not survey.project.exploration_leads.exists()
    survey.convert(force=True)
    lead = survey.project.exploration_leads.get()
    assert (lead.description, lead.headings) == (
        "decorate black, stag, !s! !down!",
        [180],
    )
    assert set(survey.project.geojsons.values_list("commit_id", flat=True)) == {
        old.pk,
        latest.pk,
    }


@pytest.mark.django_db
@pytest.mark.parametrize("latest_source", ["missing", "invalid"])
def test_unrecorded_unusable_head_cannot_import_historical_leads(
    native_survey: NativeSurvey, latest_source: str
) -> None:
    survey = native_survey
    survey.edit(survey.shot_id, comment="Historical marker !S!")
    historical = survey.commit("Historical source")
    if latest_source == "missing":
        survey.source.unlink()
    elif survey.project.type == ProjectType.COMPASS:
        (survey.source.parent / "compass.toml").write_bytes(b"invalid = [")
    else:
        survey.source.write_bytes(b"invalid native survey")
    latest = survey.commit("Unusable latest source")
    survey.project.commits.all().delete()
    if latest_source == "invalid":
        with pytest.raises(ConversionFailedError):
            survey.convert(force=True)
    else:
        survey.convert(force=True)
    assert not survey.project.exploration_leads.exists()
    assert not survey.project.exploration_lead_sources.exists()
    assert survey.project.geojsons.filter(commit_id=historical.pk).exists()
    assert survey.project.commits.filter(pk=latest.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("native_survey", ["tml"], indirect=True)
@pytest.mark.parametrize("retain_head_metadata", [False, True])
@pytest.mark.parametrize("backdated_head", [False, True], ids=["tied", "backdated"])
def test_history_uses_descendant_not_timestamp_or_metadata_creation_order(
    native_survey: NativeSurvey, retain_head_metadata: bool, backdated_head: bool
) -> None:
    survey = native_survey
    authored_at = datetime(2026, 1, 1, tzinfo=UTC)
    survey.edit(survey.shot_id, comment="Old shot !N!")
    old = survey.commit("Parent", authored_at=authored_at)
    survey.edit(survey.shot_id, comment="Removed")
    survey.edit(survey.other_id, comment="Latest shot !E!")
    latest = survey.commit(
        "Child", authored_at=authored_at - timedelta(days=int(backdated_head))
    )
    assert latest.authored_date <= old.authored_date
    if retain_head_metadata:
        survey.project.commits.exclude(pk=latest.pk).delete()
    else:
        survey.project.commits.all().delete()
    survey.convert(force=True)
    lead = survey.project.exploration_leads.get()
    assert (lead.description, lead.headings) == ("Latest shot !E!", [90])
    survey.convert(force=True)
    assert survey.project.exploration_leads.get().pk == lead.pk


@pytest.mark.django_db
@pytest.mark.parametrize(
    "native_survey", ["tml-native-uuid", "stalagmight"], indirect=True
)
def test_changed_native_uuid_learns_alias_without_overwriting_lead(
    native_survey: NativeSurvey,
) -> None:
    survey = native_survey
    survey.edit(survey.shot_id, comment="Initial !E!")
    survey.commit("Original UUID")
    survey.convert()
    lead = survey.project.exploration_leads.get()
    lead.description, lead.headings = "Edited by user", []
    lead.save()
    replacement_uuid = str(uuid4())
    survey.edit(
        survey.shot_id,
        comment="New source !N!",
        native_uuid=replacement_uuid,
        length_delta=0.1,
    )
    survey.commit("Regenerated native UUID and corrected measurement")
    survey.convert()
    lead.refresh_from_db()
    assert survey.project.exploration_leads.get().pk == lead.pk
    assert (lead.description, lead.headings) == ("Edited by user", [])
    assert survey.project.exploration_lead_sources.filter(
        kind=ExplorationLeadSource.Kind.UUID, payload=replacement_uuid, lead=lead
    ).exists()
    survey.edit(survey.shot_id, comment="New native ID !W!", renamed_id="99")
    survey.commit("Keep the learned UUID with a new native ID")
    survey.convert()
    lead.refresh_from_db()
    assert survey.project.exploration_leads.get().pk == lead.pk
    assert (lead.description, lead.headings) == ("Edited by user", [])
