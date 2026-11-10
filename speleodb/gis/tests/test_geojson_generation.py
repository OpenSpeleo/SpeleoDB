"""Explicit map executions retain real immutable Git, conversion and storage."""

from __future__ import annotations

import json
import uuid
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from unittest.mock import patch

import orjson
import pytest
from celery import Celery
from celery._state import get_current_app
from celery.contrib.testing.worker import start_worker
from celery.exceptions import SoftTimeLimitExceeded
from celery.result import EagerResult
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import connection
from django.test import TestCase
from django_celery_results.models import TaskResult
from git import Actor
from openspeleo_lib.geojson import survey_to_geojson
from openspeleo_lib.interfaces import StalagMightInterface

from speleodb.background_jobs.archive_sources import GitSource
from speleodb.background_jobs.operations import schedule_uploaded_geojson
from speleodb.common.enums import ProjectType
from speleodb.common.enums import TaskResultStatus
from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.tasks import generate_project_geojson
from speleodb.git_engine.core import GitRepo
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.surveys.models.project import ConversionFailedError
from speleodb.testing.stalagmight import NATIVE_SHOT_ID
from speleodb.testing.stalagmight import stalagmight_bytes
from speleodb.utils.exceptions import GeoJSONGenerationError

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_django.fixtures import Settings


@pytest.fixture(autouse=True)
def private_scratch(settings: Settings, tmp_path: Path) -> None:
    settings.GEOJSON_GENERATION_SCRATCH_DIR = str(tmp_path / "scratch")


@pytest.fixture
def artifact_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> FileSystemStorage:
    storage = FileSystemStorage(location=tmp_path / "artifacts")
    monkeypatch.setattr(ProjectGeoJSON._meta.get_field("file"), "storage", storage)  # noqa: SLF001
    return storage


@pytest.fixture(autouse=True)
def memory_broker() -> Generator[Celery]:
    previous = get_current_app()
    with Celery(f"geojson-tests-{uuid.uuid4()}") as app:
        app.config_from_object("django.conf:settings", namespace="CELERY")
        app.conf.update(
            broker_url="memory://",
            broker_read_url="memory://",
            broker_write_url="memory://",
            task_always_eager=False,
            result_backend="cache+memory://",
        )
        app.autodiscover_tasks(force=True)
        try:
            yield app
        finally:
            with (
                app.connection_for_write() as broker,
                broker.SimpleQueue("background_control") as queue,
            ):
                queue.clear()
            previous.set_current()


def _queue(commit: ProjectCommit) -> TaskResult:
    with TestCase.captureOnCommitCallbacks(execute=True):
        schedule_uploaded_geojson(commit.project, commit)
    return TaskResult.objects.filter(task_args=json.dumps([commit.pk])).latest(
        "date_created"
    )


def _run(commit: ProjectCommit, task: TaskResult, *, throw: bool = True) -> Any:
    return generate_project_geojson.apply(
        args=(commit.pk,),
        task_id=task.task_id,
        throw=throw,
    )


@pytest.fixture
def local_source(
    project: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> Generator[tuple[ProjectCommit, GitRepo]]:
    project.type = getattr(request, "param", ProjectType.ARIANE)
    project.exclude_geojson = False
    project.save(update_fields=["type", "exclude_geojson"])
    directory = tmp_path / "remote"
    fixture = settings.BASE_DIR / "speleodb/api/v2/tests/artifacts/test_simple.tml"
    filename, payload = (
        ("stalagmight.stalx", stalagmight_bytes())
        if project.type == ProjectType.STALAGMIGHT
        else ("ariane.tml", fixture.read_bytes())
    )
    with closing(GitRepo.init(directory)) as repository:
        (directory / filename).write_bytes(payload)
        repository.index.add([filename])
        actor = Actor("Surveyor", "surveyor@example.test")
        repository.index.commit("First survey", author=actor, committer=actor)
        commit = ProjectCommit.get_or_create_from_commit(
            project, repository.head.commit
        )
        monkeypatch.setattr(
            "speleodb.surveys.models.project.project_git_source",
            lambda project_id, **kwargs: GitSource(url=str(directory), token=""),
        )
        yield commit, repository


@pytest.mark.django_db
@pytest.mark.parametrize(
    "local_source", [ProjectType.ARIANE, ProjectType.STALAGMIGHT], indirect=True
)
def test_task_reads_requested_sha_after_new_upload(
    local_source: tuple[ProjectCommit, GitRepo],
    artifact_storage: FileSystemStorage,
) -> None:
    commit, repository = local_source
    filename = (
        "stalagmight.stalx"
        if commit.project.type == ProjectType.STALAGMIGHT
        else "ariane.tml"
    )
    expected = orjson.loads(
        orjson.dumps(commit.project.build_geojson(repository.path / filename))
    )
    generation = _queue(commit)
    (repository.path / filename).write_bytes(b"not a survey")
    repository.index.add([filename])
    actor = Actor("Surveyor", "surveyor@example.test")
    repository.index.commit("Later broken survey", author=actor, committer=actor)

    _run(commit, generation)
    generation.refresh_from_db()
    assert generation.status == TaskResultStatus.SUCCESS
    artifact = ProjectGeoJSON.objects.get(commit=commit)
    assert artifact.file.name is not None
    assert artifact_storage.exists(artifact.file.name)
    with artifact.file.open("rb") as source:
        assert orjson.loads(source.read()) == expected
    assert repository.head.commit.hexsha != commit.pk
    assert (repository.path / filename).read_bytes() == b"not a survey"
    assert not repository.is_dirty(untracked_files=True)
    revision = artifact.geojson_revision
    duplicate = _run(commit, generation)
    assert duplicate.state == "IGNORED"
    artifact.refresh_from_db()
    assert artifact.geojson_revision == revision


@pytest.mark.django_db
@pytest.mark.parametrize("local_source", [ProjectType.STALAGMIGHT], indirect=True)
def test_native_generation_uses_common_exporter(
    local_source: tuple[ProjectCommit, GitRepo],
    artifact_storage: FileSystemStorage,
) -> None:
    commit, repository = local_source
    source = repository.path / "stalagmight.stalx"
    expected = orjson.loads(
        orjson.dumps(survey_to_geojson(StalagMightInterface.from_file(source)))
    )
    generation = _queue(commit)
    _run(commit, generation)
    generation.refresh_from_db()
    assert generation.status == TaskResultStatus.SUCCESS
    artifact = ProjectGeoJSON.objects.get(commit=commit)
    with artifact.file.open("rb") as stored:
        actual = orjson.loads(stored.read())
    assert actual == expected
    anchor, entrance, branch = actual["features"]
    assert anchor["geometry"]["coordinates"] == [0.0, 0.0]
    assert entrance["id"] == str(NATIVE_SHOT_ID)
    assert entrance["properties"] == {
        "id": 1,
        "depth": 184,
        "name": "Entrance",
        "color": "#aabbcc",
    }
    # The hidden jump advances the leg's origin, the native correction points it
    # east, and the merged section starts exactly at that leg's destination.
    coordinates = entrance["geometry"]["coordinates"]
    assert coordinates[0][0] > 0
    assert coordinates[1][0] > coordinates[0][0]
    assert coordinates[0][1] == coordinates[1][1] == 0
    assert branch["geometry"]["coordinates"][0] == coordinates[1]
    assert branch["properties"]["color"] == "#336699"
    assert source.read_bytes() == stalagmight_bytes()
    assert not list(Path(settings.GEOJSON_GENERATION_SCRATCH_DIR).iterdir())


@pytest.mark.django_db
@pytest.mark.parametrize("local_source", [ProjectType.STALAGMIGHT], indirect=True)
@pytest.mark.parametrize(
    ("failure", "expected_state"),
    [
        ("unsupported_schema", TaskResultStatus.FAILURE),
        ("missing_anchor", TaskResultStatus.SUCCESS),
        ("impossible_geometry", TaskResultStatus.FAILURE),
        ("missing_source", TaskResultStatus.SUCCESS),
    ],
)
def test_native_failure_preserves_source_and_previous_artifact(
    local_source: tuple[ProjectCommit, GitRepo],
    artifact_storage: FileSystemStorage,
    failure: str,
    expected_state: str,
) -> None:
    previous, repository = local_source
    generation = _queue(previous)
    _run(previous, generation)
    artifact = ProjectGeoJSON.objects.get(commit=previous)
    original_revision = artifact.geojson_revision
    with artifact.file.open("rb") as stored:
        original_data = orjson.loads(stored.read())
    source = repository.path / "stalagmight.stalx"
    payload: bytes | None
    match failure:
        case "unsupported_schema":
            payload = stalagmight_bytes(schema_version=17)
        case "missing_anchor":
            payload = stalagmight_bytes(anchored=False)
        case "impossible_geometry":
            payload = stalagmight_bytes(length=1.0)
        case "missing_source":
            payload = None
        case _:
            raise AssertionError(failure)
    if payload is None:
        repository.index.remove([source.name], working_tree=True)
    else:
        source.write_bytes(payload)
        repository.index.add([source.name])
    actor = Actor("Surveyor", "surveyor@example.test")
    repository.index.commit(
        "Unconvertible native source", author=actor, committer=actor
    )
    commit = ProjectCommit.get_or_create_from_commit(
        previous.project, repository.head.commit
    )
    generation = _queue(commit)
    result = _run(commit, generation, throw=False)
    assert result.failed() is (expected_state == TaskResultStatus.FAILURE)
    generation.refresh_from_db()
    assert generation.status == expected_state
    assert json.loads(generation.meta or "{}")["summary"]["failed"] == (
        1 if expected_state == TaskResultStatus.FAILURE else 0
    )
    assert not ProjectGeoJSON.objects.filter(commit=commit).exists()
    artifact.refresh_from_db()
    assert artifact.geojson_revision == original_revision
    with artifact.file.open("rb") as stored:
        assert orjson.loads(stored.read()) == original_data
    assert repository.head.commit.hexsha == commit.pk
    if payload is not None:
        assert source.read_bytes() == payload
        blob = repository.commit(commit.pk).tree / source.name
        assert blob.blob.data_stream.read() == payload
    assert not list(Path(settings.GEOJSON_GENERATION_SCRATCH_DIR).iterdir())


@pytest.mark.django_db
def test_soft_timeout_is_durable_and_still_escapes_to_celery(
    local_source: tuple[ProjectCommit, GitRepo],
) -> None:
    commit, _ = local_source
    generation = _queue(commit)
    with (
        patch.object(Project, "build_geojson", side_effect=SoftTimeLimitExceeded),
        pytest.raises(SoftTimeLimitExceeded),
    ):
        _run(commit, generation)
    generation.refresh_from_db()
    assert generation.status == TaskResultStatus.FAILURE
    assert json.loads(generation.meta or "{}")["error_type"] == "SoftTimeLimitExceeded"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("local_source", "invalid_geometry"),
    [(ProjectType.ARIANE, False), (ProjectType.STALAGMIGHT, True)],
    indirect=["local_source"],
)
def test_worker_consumes_committed_job_asynchronously(
    local_source: tuple[ProjectCommit, GitRepo],
    artifact_storage: FileSystemStorage,
    memory_broker: Celery,
    invalid_geometry: bool,
) -> None:
    assert connection.vendor == "postgresql", (
        "This integration test uses an independent worker DB connection"
    )
    commit, repository = local_source
    if invalid_geometry:
        source = repository.path / "stalagmight.stalx"
        source.write_bytes(stalagmight_bytes(length=1.0))
        repository.index.add([source.name])
        actor = Actor("Surveyor", "surveyor@example.test")
        repository.index.commit("Invalid geometry", author=actor, committer=actor)
        commit = ProjectCommit.get_or_create_from_commit(
            commit.project, repository.head.commit
        )
    generation = _queue(commit)
    queue = f"test-geojson-{uuid.uuid4().hex}"
    # Memory transport otherwise sleeps a full second between deliveries.
    # Keep actual asynchronous execution without that unrelated polling delay.
    memory_broker.conf.CELERY_BROKER_TRANSPORT_OPTIONS = {
        **memory_broker.conf.broker_transport_options,
        "polling_interval": 0.05,
    }
    with start_worker(memory_broker, queues=[queue], perform_ping_check=False):
        result = generate_project_geojson.apply_async(
            args=(commit.pk,),
            task_id=generation.task_id,
            queue=queue,
        )
        assert not isinstance(result, EagerResult)
        outcome = result.get(timeout=30, interval=0.05, propagate=False)
        if invalid_geometry:
            assert isinstance(outcome, ConversionFailedError)
            assert outcome.summary.failed == 1
            assert result.failed()
        else:
            assert outcome["generated"] == 1
            assert result.successful()
    generation.refresh_from_db()
    if invalid_geometry:
        assert generation.status == TaskResultStatus.FAILURE
        assert not ProjectGeoJSON.objects.filter(commit=commit).exists()
    else:
        assert generation.status == TaskResultStatus.SUCCESS
        artifact = ProjectGeoJSON.objects.get(commit=commit)
        assert artifact.file.name is not None
        assert artifact_storage.exists(artifact.file.name)


@pytest.mark.django_db
@pytest.mark.parametrize("local_source", [ProjectType.STALAGMIGHT], indirect=True)
def test_history_continues_independent_revisions_then_fails(
    local_source: tuple[ProjectCommit, GitRepo],
    artifact_storage: FileSystemStorage,
) -> None:
    first, repository = local_source
    source = repository.path / "stalagmight.stalx"
    source.write_bytes(stalagmight_bytes(length=1.0))
    repository.index.add([source.name])
    actor = Actor("Surveyor", "surveyor@example.test")
    repository.index.commit(
        "Impossible later measurements", author=actor, committer=actor
    )
    failing_sha = repository.head.commit.hexsha
    with pytest.raises(ConversionFailedError) as raised:
        first.project.build_geojsons()
    summary = raised.value.summary
    assert summary.processed == 2  # noqa: PLR2004 - One valid and one invalid revision.
    assert summary.generated == 1
    assert summary.failed == 1
    assert isinstance(raised.value.__cause__, GeoJSONGenerationError)
    assert raised.value.__cause__.__cause__ is not None
    assert ProjectGeoJSON.objects.filter(commit=first).exists()
    assert not ProjectGeoJSON.objects.filter(commit_id=failing_sha).exists()
    artifact = ProjectGeoJSON.objects.get(commit=first)
    assert artifact.file.name is not None
    assert artifact_storage.exists(artifact.file.name)
