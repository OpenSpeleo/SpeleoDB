"""Durable map work uses SQL, local Git, and temporary storage, never GitLab."""

from __future__ import annotations

import os
import uuid
from contextlib import closing
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING
from typing import Any
from unittest.mock import patch

import orjson
import pytest
from celery.contrib.testing.worker import start_worker
from celery.exceptions import SoftTimeLimitExceeded
from celery.result import EagerResult
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.db import connection
from django.db import transaction
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
from git import Actor
from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError

from config.celery_app import app
from speleodb.background_jobs.archive_sources import GitSource
from speleodb.common.enums import ProjectType
from speleodb.gis.admin.project_geojson_generation import GeoJSONGenerationForm
from speleodb.gis.geojson_generation import GeoJSONOwnershipLostError
from speleodb.gis.geojson_generation import claim_geojson_generation
from speleodb.gis.geojson_generation import cleanup_geojson_work
from speleodb.gis.geojson_generation import dispatch_pending_geojsons
from speleodb.gis.geojson_generation import finish_geojson_generation
from speleodb.gis.geojson_generation import mark_geojson_ready
from speleodb.gis.geojson_generation import request_geojson_generation
from speleodb.gis.geojson_generation import reserve_geojson_object
from speleodb.gis.geojson_generation import retry_geojson_generation
from speleodb.gis.models import GeoJSONGenerationState
from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.models import ProjectGeoJSONGeneration
from speleodb.gis.project_geojson_services import replace_project_geojson
from speleodb.gis.tasks import generate_project_geojson
from speleodb.git_engine.core import GitRepo
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from pytest_django.fixtures import Settings

pytestmark = pytest.mark.django_db
PUBLISH = "speleodb.gis.geojson_generation.current_app.send_task"
POINT_DATA: dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [1, 2]},
            "properties": {},
        }
    ],
}


@pytest.fixture(autouse=True)
def private_scratch(settings: Settings, tmp_path: Path) -> None:
    settings.GEOJSON_GENERATION_SCRATCH_DIR = str(tmp_path / "scratch")


@pytest.fixture
def commit(project: Project) -> ProjectCommit:
    project.type = ProjectType.ARIANE
    project.exclude_geojson = False
    project.save(update_fields=["type", "exclude_geojson"])
    return ProjectCommit.objects.create(
        id="a" * 40,
        project=project,
        author_name="Surveyor",
        author_email="surveyor@example.test",
        authored_date=timezone.now(),
        message="Survey upload",
    )


@pytest.fixture
def artifact_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> FileSystemStorage:
    storage = FileSystemStorage(location=tmp_path / "artifacts")
    field = ProjectGeoJSON._meta.get_field("file")  # noqa: SLF001
    monkeypatch.setattr(field, "storage", storage)
    return storage


def _queue(commit: ProjectCommit) -> ProjectGeoJSONGeneration:
    generation = request_geojson_generation(commit.project, commit)
    with patch(PUBLISH) as publish:
        dispatch_pending_geojsons()
    generation.refresh_from_db()
    publish.assert_called_once_with(
        "speleodb.gis.tasks.generate_project_geojson",
        args=[commit.pk, str(generation.token)],
        task_id=str(generation.token),
        queue="background_control",
        retry=False,
    )
    return generation


def _running(commit: ProjectCommit) -> ProjectGeoJSONGeneration:
    generation = _queue(commit)
    claimed = claim_geojson_generation(commit.pk, str(generation.token))
    assert claimed is not None
    return claimed


def test_request_is_durable_idempotent_and_never_calls_broker(
    commit: ProjectCommit,
) -> None:
    with patch(PUBLISH, side_effect=AssertionError("No broker in requests")):
        first = request_geojson_generation(commit.project, commit)
        second = request_geojson_generation(commit.project, commit)
    assert first.pk == second.pk
    assert first.state == GeoJSONGenerationState.PENDING
    assert ProjectGeoJSONGeneration.objects.count() == 1
    assert first.attempts == 0


def test_request_rollback_removes_pending_work(commit: ProjectCommit) -> None:
    with transaction.atomic():
        request_geojson_generation(commit.project, commit)
        transaction.set_rollback(True)
    with patch(PUBLISH) as publish:
        dispatch_pending_geojsons()
    publish.assert_not_called()
    assert not ProjectGeoJSONGeneration.objects.exists()


def test_excluded_project_never_dispatches(commit: ProjectCommit) -> None:
    commit.project.exclude_geojson = True
    generation = request_geojson_generation(commit.project, commit)
    assert generation.state == GeoJSONGenerationState.SKIPPED
    with patch(PUBLISH) as publish:
        dispatch_pending_geojsons()
    publish.assert_not_called()


def test_broker_failure_retains_work_without_consuming_execution_budget(
    commit: ProjectCommit, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    generation = request_geojson_generation(commit.project, commit)
    with patch(PUBLISH, side_effect=ConnectionError("broker offline")):
        dispatch_pending_geojsons()
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.PENDING
    assert generation.attempts == 0
    assert generation.dispatch_attempts == 1
    assert generation.last_error_code == "broker_unavailable"
    assert generation.next_attempt_at == now + timedelta(seconds=60)
    with patch(PUBLISH) as publish:
        dispatch_pending_geojsons()
    publish.assert_not_called()
    now += timedelta(seconds=60)
    with patch(PUBLISH) as publish:
        dispatch_pending_geojsons()
    publish.assert_called_once()
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.QUEUED


def test_ambiguous_delivery_does_not_reset_claimed_execution(
    commit: ProjectCommit,
) -> None:
    generation = request_geojson_generation(commit.project, commit)

    def claim_then_fail(*args: Any, **kwargs: Any) -> None:
        assert claim_geojson_generation(*kwargs["args"]) is not None
        raise ConnectionError("reply lost after acceptance")

    with patch(PUBLISH, side_effect=claim_then_fail):
        dispatch_pending_geojsons()
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.RUNNING
    assert generation.attempts == 1


def test_duplicate_delivery_claims_once_and_expired_queue_token_is_ignored(
    commit: ProjectCommit, monkeypatch: pytest.MonkeyPatch
) -> None:
    generation = _queue(commit)
    old_token = str(generation.token)
    now = generation.lease_expires_at
    assert now is not None
    monkeypatch.setattr(timezone, "now", lambda: now)
    assert claim_geojson_generation(commit.pk, old_token) is None
    with patch(PUBLISH):
        dispatch_pending_geojsons()
    generation.refresh_from_db()
    assert str(generation.token) != old_token
    assert claim_geojson_generation(commit.pk, old_token) is None
    assert claim_geojson_generation(commit.pk, str(generation.token)) is not None
    assert claim_geojson_generation(commit.pk, str(generation.token)) is None


def test_worker_lease_recovers_and_stops_after_three_attempts(
    commit: ProjectCommit, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    generation = request_geojson_generation(commit.project, commit)
    for attempt in range(1, settings.GEOJSON_GENERATION_MAX_ATTEMPTS + 1):
        with patch(PUBLISH):
            dispatch_pending_geojsons()
        generation.refresh_from_db()
        assert claim_geojson_generation(commit.pk, str(generation.token)) is not None
        generation.refresh_from_db()
        assert generation.attempts == attempt
        assert generation.lease_expires_at is not None
        now = generation.lease_expires_at
        with patch(PUBLISH) as publish:
            dispatch_pending_geojsons()
        publish.assert_not_called()
        generation.refresh_from_db()
        if generation.next_attempt_at is not None:
            now = generation.next_attempt_at
    assert generation.state == GeoJSONGenerationState.FAILED
    assert generation.last_error_code == "worker_timeout"


def test_stale_result_cannot_publish_and_new_blob_is_removed(
    commit: ProjectCommit,
    artifact_storage: FileSystemStorage,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generation = _running(commit)
    deadline = generation.lease_expires_at
    assert deadline is not None
    monkeypatch.setattr(timezone, "now", lambda: deadline)
    with pytest.raises(GeoJSONOwnershipLostError):
        replace_project_geojson(
            commit.project,
            commit,
            POINT_DATA,
            before_publish=partial(
                mark_geojson_ready, commit.pk, str(generation.token)
            ),
        )
    assert not ProjectGeoJSON.objects.exists()
    assert not list(tmp_path.rglob("*.json"))
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.RUNNING


@pytest.mark.parametrize("maintenance", [False, True])
def test_ready_state_and_artifact_insert_roll_back_together(
    commit: ProjectCommit, artifact_storage: FileSystemStorage, maintenance: bool
) -> None:
    generation = _running(commit)
    with (
        patch.object(ProjectGeoJSON, "save", side_effect=RuntimeError("insert failed")),
        pytest.raises(RuntimeError, match="insert failed"),
    ):
        replace_project_geojson(
            commit.project,
            commit,
            POINT_DATA,
            before_publish=None
            if maintenance
            else partial(mark_geojson_ready, commit.pk, str(generation.token)),
        )
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.RUNNING
    assert not ProjectGeoJSON.objects.exists()


def test_retry_recovers_missing_row_and_terminal_failure(commit: ProjectCommit) -> None:
    generation = retry_geojson_generation(commit)
    assert generation.state == GeoJSONGenerationState.PENDING
    generation.state = GeoJSONGenerationState.FAILED
    generation.attempts = 3
    generation.last_error_code = "invalid_survey"
    generation.save()
    old_token = generation.token
    generation = retry_geojson_generation(commit)
    assert generation.state == GeoJSONGenerationState.PENDING
    assert generation.attempts == 0
    assert generation.last_error_code == ""
    assert generation.token != old_token


def test_terminal_failure_retains_previous_artifact(
    commit: ProjectCommit, artifact_storage: FileSystemStorage
) -> None:
    previous = ProjectCommit.objects.create(
        id="b" * 40,
        project=commit.project,
        author_name=commit.author_name,
        author_email=commit.author_email,
        authored_date=commit.authored_date - timedelta(days=1),
        message="Previous source",
    )
    artifact = replace_project_geojson(commit.project, previous, POINT_DATA)
    generation = _running(commit)
    finish_geojson_generation(
        commit.pk,
        str(generation.token),
        code="invalid_survey",
        message="Longitude is invalid.",
    )
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.FAILED
    assert ProjectGeoJSON.objects.get(commit=previous).file.name == artifact.file.name
    assert artifact.file.name is not None
    assert artifact_storage.exists(artifact.file.name)


@pytest.fixture
def local_source(
    project: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[tuple[ProjectCommit, GitRepo]]:
    project.type = ProjectType.ARIANE
    project.exclude_geojson = False
    project.save(update_fields=["type", "exclude_geojson"])
    directory = tmp_path / "remote"
    fixture = settings.BASE_DIR / "speleodb/api/v2/tests/artifacts/test_simple.tml"
    with closing(GitRepo.init(directory)) as repository:
        (directory / "ariane.tml").write_bytes(fixture.read_bytes())
        repository.index.add(["ariane.tml"])
        actor = Actor("Surveyor", "surveyor@example.test")
        repository.index.commit("First survey", author=actor, committer=actor)
        commit = ProjectCommit.get_or_create_from_commit(
            project, repository.head.commit
        )
        monkeypatch.setattr(
            "speleodb.gis.tasks.project_git_source",
            lambda project_id: GitSource(url=str(directory), token=""),
        )
        yield commit, repository


def test_task_reads_requested_sha_after_new_upload(
    local_source: tuple[ProjectCommit, GitRepo],
    artifact_storage: FileSystemStorage,
) -> None:
    commit, repository = local_source
    generation = _queue(commit)
    (repository.path / "ariane.tml").write_bytes(b"not a survey")
    repository.index.add(["ariane.tml"])
    actor = Actor("Surveyor", "surveyor@example.test")
    repository.index.commit("Later broken survey", author=actor, committer=actor)

    def reject_shared_checkout(self: Project) -> None:
        pytest.fail("Worker must not access a shared project checkout")

    with patch.object(Project, "git_repo", property(reject_shared_checkout)):
        generate_project_geojson.run(commit.pk, str(generation.token))
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.READY
    artifact = ProjectGeoJSON.objects.get(commit=commit)
    assert artifact.file.name is not None
    assert artifact_storage.exists(artifact.file.name)
    assert repository.head.commit.hexsha != commit.pk
    revision = artifact.geojson_revision
    generate_project_geojson.run(commit.pk, str(generation.token))
    artifact.refresh_from_db()
    assert artifact.geojson_revision == revision


def test_validation_failure_has_bounded_station_notes_without_raw_payload(
    local_source: tuple[ProjectCommit, GitRepo],
) -> None:
    commit, _ = local_source
    generation = _queue(commit)

    class Coordinate(BaseModel):
        longitude: float = Field(ge=-180, le=180)

    with pytest.raises(ValidationError) as captured:
        Coordinate(longitude=-183.47)
    error = captured.value
    error.add_note("Section entrance; station 0: longitude -183.47 outside [-180,180]")
    error.add_note("x" * 5000)
    with patch.object(Project, "build_geojson", side_effect=error):
        generate_project_geojson.run(commit.pk, str(generation.token))
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.FAILED
    assert generation.last_error_code == "invalid_survey"
    assert "station 0" in generation.last_error
    assert len(generation.last_error) <= 2000  # noqa: PLR2004
    assert "Input should" not in generation.last_error
    assert generation.attempts == 1


def test_soft_timeout_is_durable_and_still_escapes_to_celery(
    local_source: tuple[ProjectCommit, GitRepo],
) -> None:
    commit, _ = local_source
    generation = _queue(commit)
    with (
        patch.object(Project, "build_geojson", side_effect=SoftTimeLimitExceeded),
        pytest.raises(SoftTimeLimitExceeded),
    ):
        generate_project_geojson.run(commit.pk, str(generation.token))
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.PENDING
    assert generation.last_error_code == "worker_timeout"
    assert generation.next_attempt_at is not None


def test_scheduler_and_task_limits() -> None:
    call_command("install_background_schedules")
    call_command("install_background_schedules")
    schedule = PeriodicTask.objects.get(name="project-geojson-dispatch")
    assert schedule.task == "speleodb.gis.tasks.dispatch_project_geojsons"
    assert schedule.queue == "background_control"
    assert schedule.interval is not None
    assert schedule.interval.every == 60  # noqa: PLR2004
    assert generate_project_geojson.soft_time_limit == 300  # noqa: PLR2004
    assert generate_project_geojson.time_limit == 360  # noqa: PLR2004


def test_journal_recovers_unpublished_blob_after_hard_kill(
    commit: ProjectCommit,
    artifact_storage: FileSystemStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generation = _running(commit)
    token = str(generation.token)
    key = f"{commit.project_id}/abandoned.json"
    reserve_geojson_object(commit.pk, token, key)
    # Simulate process death after S3 accepted bytes but before SQL publication.
    artifact_storage.save(key, ContentFile(b"abandoned map"))
    generation.refresh_from_db()
    assert generation.lease_expires_at is not None
    later = generation.lease_expires_at + timedelta(
        seconds=settings.GEOJSON_GENERATION_CLEANUP_GRACE_SECONDS
    )
    cleanup_geojson_work()
    assert artifact_storage.exists(key)
    monkeypatch.setattr(timezone, "now", lambda: later)
    cleanup_geojson_work()
    assert not artifact_storage.exists(key)
    generation.refresh_from_db()
    assert generation.unpublished_objects == []


def test_failed_cleanup_does_not_starve_later_journals(
    commit: ProjectCommit,
    artifact_storage: FileSystemStorage,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.GEOJSON_GENERATION_DISPATCH_BATCH = 1
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    newer = ProjectCommit.objects.create(
        id="b" * 40,
        project=commit.project,
        author_name=commit.author_name,
        author_email=commit.author_email,
        authored_date=commit.authored_date,
        message="Later abandoned upload",
    )
    for index, source in enumerate((commit, newer)):
        key = f"{source.project_id}/{source.pk}.json"
        artifact_storage.save(key, ContentFile(b"abandoned"))
        ProjectGeoJSONGeneration.objects.create(
            commit=source,
            state=GeoJSONGenerationState.FAILED,
            updated_at=now - timedelta(days=2 - index),
            unpublished_objects=[
                {"key": key, "token": "expired", "cleanup_after": now.isoformat()}
            ],
        )
    delete = artifact_storage.delete
    blocked_key = f"{commit.project_id}/{commit.pk}.json"
    newer_key = f"{newer.project_id}/{newer.pk}.json"

    def delete_except_blocked(key: str) -> None:
        if key == blocked_key:
            raise OSError("Deletion permanently denied for this object")
        delete(key)

    monkeypatch.setattr(artifact_storage, "delete", delete_except_blocked)
    cleanup_geojson_work()
    assert artifact_storage.exists(newer_key)
    cleanup_geojson_work()
    assert not artifact_storage.exists(newer_key)
    assert artifact_storage.exists(blocked_key)
    assert ProjectGeoJSONGeneration.objects.get(pk=commit.pk).unpublished_objects
    assert ProjectGeoJSONGeneration.objects.get(pk=newer.pk).unpublished_objects == []


@pytest.mark.parametrize("failed", [False, True])
def test_maintenance_publication_reconciles_worker_and_preserves_cleanup(
    commit: ProjectCommit, artifact_storage: FileSystemStorage, failed: bool
) -> None:
    generation = _running(commit)
    token = str(generation.token)
    reserve_geojson_object(commit.pk, token, "abandoned.json")
    if failed:
        finish_geojson_generation(
            commit.pk, token, code="invalid_survey", message="Previous exporter failed"
        )
    artifact = replace_project_geojson(commit.project, commit, POINT_DATA)
    # A late worker failure must not undo a successful maintenance publication.
    finish_geojson_generation(
        commit.pk, token, code="invalid_survey", message="Superseded worker failed"
    )
    with pytest.raises(GeoJSONOwnershipLostError):
        mark_geojson_ready(commit.pk, token)
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.READY
    assert generation.last_error == ""
    assert generation.lease_expires_at is None
    assert generation.unpublished_objects[0]["key"] == "abandoned.json"
    assert ProjectGeoJSON.objects.get(commit=commit).file.name == artifact.file.name


def test_failed_maintenance_replacement_preserves_artifact_and_status(
    commit: ProjectCommit, artifact_storage: FileSystemStorage
) -> None:
    previous = replace_project_geojson(commit.project, commit, POINT_DATA)
    generation = ProjectGeoJSONGeneration.objects.create(
        commit=commit,
        state=GeoJSONGenerationState.FAILED,
        last_error="Earlier generation failure",
    )
    with (
        patch.object(ProjectGeoJSON, "save", side_effect=RuntimeError("insert failed")),
        pytest.raises(RuntimeError, match="insert failed"),
    ):
        replace_project_geojson(commit.project, commit, POINT_DATA)
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.FAILED
    assert generation.last_error == "Earlier generation failure"
    assert ProjectGeoJSON.objects.get(commit=commit).file.name == previous.file.name
    assert previous.file.name is not None
    assert artifact_storage.exists(previous.file.name)


def test_journal_never_deletes_published_or_live_objects(
    commit: ProjectCommit,
    artifact_storage: FileSystemStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generation = _running(commit)
    artifact = replace_project_geojson(commit.project, commit, POINT_DATA)
    now = timezone.now()
    ProjectGeoJSONGeneration.objects.filter(pk=commit.pk).update(
        unpublished_objects=[
            {
                "key": artifact.file.name,
                "token": "old",
                "cleanup_after": now.isoformat(),
            }
        ]
    )
    cleanup_geojson_work()
    assert artifact.file.name is not None
    assert artifact_storage.exists(artifact.file.name)
    generation.refresh_from_db()
    assert generation.unpublished_objects == []


def test_ready_publication_clears_upload_journal_atomically(
    commit: ProjectCommit, artifact_storage: FileSystemStorage
) -> None:
    generation = _running(commit)
    token = str(generation.token)
    replace_project_geojson(
        commit.project,
        commit,
        POINT_DATA,
        before_upload=partial(reserve_geojson_object, commit.pk, token),
        before_publish=partial(mark_geojson_ready, commit.pk, token),
    )
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.READY
    assert generation.unpublished_objects == []


def test_abandoned_scratch_cleanup_preserves_live_work(
    commit: ProjectCommit, tmp_path: Path
) -> None:
    generation = _running(commit)
    root = tmp_path / "scratch"
    root.mkdir()
    abandoned = root / f"{uuid.uuid4()}-abandoned"
    live = root / f"{generation.token}-live"
    unrelated = root / "unrelated"
    now = timezone.now()
    cutoff = now.timestamp() - settings.GEOJSON_GENERATION_HARD_TIME_LIMIT - 301
    for directory in (abandoned, live, unrelated):
        directory.mkdir()
        (directory / "source").write_bytes(b"survey")
        os.utime(directory, (cutoff, cutoff))
    cleanup_geojson_work()
    assert not abandoned.exists()
    assert live.exists()
    assert unrelated.exists()


def test_admin_add_validates_excluded_commit(commit: ProjectCommit) -> None:
    commit.project.exclude_geojson = True
    commit.project.save(update_fields=["exclude_geojson"])
    form = GeoJSONGenerationForm(data={"commit": commit.pk})
    assert not form.is_valid()
    assert "excluded" in str(form.errors["commit"])


def test_existing_artifact_winner_retains_failed_cleanup_journal(
    commit: ProjectCommit,
    artifact_storage: FileSystemStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generation = _running(commit)
    token = str(generation.token)
    # A legacy/direct artifact writer does not reconcile generation ownership.
    previous = ProjectGeoJSON.objects.create(
        project=commit.project,
        commit=commit,
        file=ContentFile(orjson.dumps(POINT_DATA), name="existing.geojson"),
    )
    later = timezone.now() + timedelta(
        seconds=settings.GEOJSON_GENERATION_HARD_TIME_LIMIT
        + settings.GEOJSON_GENERATION_CLEANUP_GRACE_SECONDS
    )
    with patch.object(artifact_storage, "delete", side_effect=OSError("offline")):
        result = replace_project_geojson(
            commit.project,
            commit,
            POINT_DATA,
            replace_existing=False,
            before_upload=partial(reserve_geojson_object, commit.pk, token),
            before_publish=partial(mark_geojson_ready, commit.pk, token),
        )
    assert result.file.name == previous.file.name
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.READY
    assert len(generation.unpublished_objects) == 1
    abandoned_key = generation.unpublished_objects[0]["key"]
    assert artifact_storage.exists(abandoned_key)
    monkeypatch.setattr(timezone, "now", lambda: later)
    cleanup_geojson_work()
    assert not artifact_storage.exists(abandoned_key)
    assert previous.file.name is not None
    assert artifact_storage.exists(previous.file.name)


@pytest.mark.django_db(transaction=True)
def test_worker_consumes_committed_job_asynchronously(
    local_source: tuple[ProjectCommit, GitRepo],
    artifact_storage: FileSystemStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if connection.vendor != "postgresql":
        pytest.skip("This integration test uses an independent worker DB connection")
    commit, _ = local_source
    generation = _queue(commit)
    monkeypatch.setattr(app.conf, "task_always_eager", False)
    queue = f"test-geojson-{uuid.uuid4().hex}"
    with start_worker(app, queues=[queue], perform_ping_check=False):
        result = generate_project_geojson.apply_async(
            args=(commit.pk, str(generation.token)),
            task_id=str(generation.token),
            queue=queue,
        )
        assert not isinstance(result, EagerResult)
        assert result.get(timeout=30) is None
        assert result.successful()
    generation.refresh_from_db()
    assert generation.state == GeoJSONGenerationState.READY
    assert generation.unpublished_objects == []
    artifact = ProjectGeoJSON.objects.get(commit=commit)
    assert artifact.file.name is not None
    assert artifact_storage.exists(artifact.file.name)


@pytest.mark.parametrize("operation", ["claim", "reserve", "publish"])
def test_deadline_is_rechecked_after_acquiring_the_row_lock(
    commit: ProjectCommit, operation: str
) -> None:
    generation = _queue(commit) if operation == "claim" else _running(commit)
    deadline = generation.lease_expires_at
    assert deadline is not None
    initial_state = generation.state
    token = str(generation.token)
    # First clock read constructs the SQL predicate. Time advances while the
    # SELECT FOR UPDATE acquires its row, before the second application check.
    with patch(
        "speleodb.gis.geojson_generation.timezone.now",
        side_effect=(deadline - timedelta(seconds=1), deadline),
    ):
        if operation == "claim":
            assert claim_geojson_generation(commit.pk, token) is None
        elif operation == "reserve":
            with pytest.raises(GeoJSONOwnershipLostError):
                reserve_geojson_object(commit.pk, token, "unused.json")
        else:
            with pytest.raises(GeoJSONOwnershipLostError):
                mark_geojson_ready(commit.pk, token)
    generation.refresh_from_db()
    assert generation.state == initial_state
    assert generation.unpublished_objects == []
