"""Exercise maintenance task delivery without running against development data."""

from __future__ import annotations

import os
import signal
import sys
import uuid
from typing import TYPE_CHECKING

import pytest
from celery import Celery
from celery._state import get_current_app
from celery.contrib.testing.worker import start_worker
from celery.exceptions import SoftTimeLimitExceeded
from celery.result import EagerResult
from compass_lib.io import load_project
from django.conf import settings
from django.test import override_settings
from openspeleo_lib.interfaces import ArianeInterface

from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.common.enums import ProjectType
from speleodb.surveys.models import Project
from speleodb.surveys.tasks import refresh_all_projects_geojson
from speleodb.surveys.tasks import refresh_project_geojson
from speleodb.utils.exceptions import reraise_task_timeout

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from types import FrameType


@pytest.mark.parametrize(
    ("project_type", "filename"),
    [(ProjectType.ARIANE, "test_simple.tml"), (ProjectType.COMPASS, "sample.mak")],
)
def test_source_timeout_is_not_treated_as_invalid_survey(
    project_type: ProjectType, filename: str
) -> None:
    source = (
        settings.BASE_DIR / "speleodb" / "api" / "v2" / "tests" / "artifacts" / filename
    )
    loader_code = (
        ArianeInterface.from_file.__code__
        if project_type == ProjectType.ARIANE
        else load_project.__code__
    )
    signal_delivered = False

    def soft_timeout(_signum: int, _frame: FrameType | None) -> None:
        nonlocal signal_delivered
        signal_delivered = True
        raise SoftTimeLimitExceeded

    def observe_loader(frame: FrameType, event: str, _argument: object) -> None:
        if event == "call" and frame.f_code is loader_code and not signal_delivered:
            os.kill(os.getpid(), signal.SIGUSR1)

    # Observe the actual loader entry while build_geojson's exception handler is
    # active. A real OS signal interrupts conversion without replacing a parser
    # or relying on file-open events from Ariane's native reader.
    previous_profile = sys.getprofile()
    previous_handler = signal.signal(signal.SIGUSR1, soft_timeout)
    try:
        sys.setprofile(observe_loader)
        with pytest.raises(SoftTimeLimitExceeded):
            Project(type=project_type).build_geojson(source)
        assert signal_delivered
    finally:
        sys.setprofile(previous_profile)
        signal.signal(signal.SIGUSR1, previous_handler)
    assert sys.getprofile() is previous_profile
    assert signal.getsignal(signal.SIGUSR1) == previous_handler


@pytest.mark.parametrize("chain_attribute", ["__cause__", "__context__"])
def test_nested_timeout_is_preserved(chain_attribute: str) -> None:
    timeout = SoftTimeLimitExceeded()
    wrapper = ValueError("Conversion interrupted")
    setattr(wrapper, chain_attribute, timeout)
    outer = RuntimeError("Export failed")
    setattr(outer, chain_attribute, wrapper)
    with pytest.raises(SoftTimeLimitExceeded) as raised:
        reraise_task_timeout(outer)
    assert raised.value is timeout


def test_ordinary_error_cycles_do_not_prevent_batch_error_isolation() -> None:
    error = ValueError("Invalid survey")
    wrapper = RuntimeError("Conversion failed")
    error.__cause__ = wrapper
    wrapper.__context__ = error
    reraise_task_timeout(error)


@pytest.fixture
def rebuild_app() -> Iterator[Celery]:
    previous = get_current_app()
    with Celery(f"geojson-rebuild-{uuid.uuid4()}") as application:
        application.config_from_object("django.conf:settings", namespace="CELERY")
        application.conf.update(
            task_always_eager=False,
            task_default_queue=f"test-geojson-rebuild-{uuid.uuid4().hex}",
            task_routes={},
        )
        application.autodiscover_tasks(force=True)
        try:
            yield application
        finally:
            previous.set_current()


@pytest.mark.django_db
def test_coordinator_only_enqueues_one_forced_child_per_eligible_project(
    rebuild_app: Celery, tmp_path: Path
) -> None:
    assert not Project.objects.exists()
    assert refresh_all_projects_geojson.apply(throw=True).get() == {
        "enqueued": 0,
        "tasks": [],
    }
    assert not Project.objects.exists()
    projects = ProjectFactory.create_batch(3, exclude_geojson=False)
    ProjectFactory.create(exclude_geojson=True)
    expected_ids = {str(project.pk) for project in projects}
    with override_settings(GEOJSON_GENERATION_SCRATCH_DIR=str(tmp_path)):
        result = refresh_all_projects_geojson.apply(throw=True).get()
    assert result["enqueued"] == len(expected_ids)
    assert {item["project_id"] for item in result["tasks"]} == expected_ids
    expected_tasks = {item["task_id"]: item["project_id"] for item in result["tasks"]}
    assert len(expected_tasks) == len(expected_ids)
    # No worker is running: real broker messages prove the coordinator returns
    # without cloning, converting or waiting for child execution.
    with (
        rebuild_app.connection_for_read() as connection,
        connection.SimpleQueue(rebuild_app.conf.task_default_queue) as queue,
    ):
        for _ in projects:
            message = queue.get(block=False)
            assert message.headers["task"] == refresh_project_geojson.name
            assert message.payload[0] == [expected_tasks.pop(message.headers["id"])]
            assert message.payload[1] == {"force_recompute": True}
            message.ack()
        assert queue.qsize() == 0
    assert not expected_tasks
    assert not list(tmp_path.iterdir())


@pytest.mark.django_db(transaction=True)
def test_async_rebuild_rechecks_scope_isolates_failures_and_handles_empty_scope(
    rebuild_app: Celery, tmp_path: Path
) -> None:
    failing: Project = ProjectFactory.create(exclude_geojson=False)
    excluded: Project = ProjectFactory.create(exclude_geojson=False)
    deleted: Project = ProjectFactory.create(exclude_geojson=False)
    deleted_id = str(deleted.pk)
    batch = refresh_all_projects_geojson.apply(throw=True).get()
    excluded.exclude_geojson = True
    excluded.save(update_fields=["exclude_geojson"])
    deleted.delete()
    results = {
        item["project_id"]: rebuild_app.AsyncResult(item["task_id"])
        for item in batch["tasks"]
    }
    with (
        override_settings(
            GITLAB_HOST_URL="invalid/host", GEOJSON_GENERATION_SCRATCH_DIR=str(tmp_path)
        ),
        start_worker(
            rebuild_app,
            queues=[rebuild_app.conf.task_default_queue],
            perform_ping_check=False,
        ),
    ):
        assert results[str(excluded.pk)].get(timeout=15) == "skipped"
        assert results[deleted_id].get(timeout=15) == "skipped"
        results[str(failing.pk)].get(timeout=15, propagate=False)
        assert results[str(failing.pk)].failed()

        # Reuse this actual worker to prove coordinator delivery with no
        # eligible projects, after its children have completed independently.
        Project.objects.filter(pk=failing.pk).update(exclude_geojson=True)
        empty_result = refresh_all_projects_geojson.delay()
        assert not isinstance(empty_result, EagerResult)
        assert empty_result.get(timeout=15) == {"enqueued": 0, "tasks": []}
        assert empty_result.successful()
        assert not Project.objects.filter(exclude_geojson=False).exists()
        assert set(Project.objects.values_list("pk", flat=True)) == {
            failing.pk,
            excluded.pk,
        }
    assert not list(tmp_path.iterdir())


def test_project_rebuild_has_maintenance_limits_and_coordinator_does_not() -> None:
    assert refresh_project_geojson.soft_time_limit == (
        settings.GEOJSON_REBUILD_SOFT_TIME_LIMIT
    )
    assert (
        refresh_project_geojson.time_limit == settings.GEOJSON_REBUILD_HARD_TIME_LIMIT
    )
    assert refresh_all_projects_geojson.soft_time_limit != (
        refresh_project_geojson.soft_time_limit
    )
    assert (
        0
        < settings.GEOJSON_REBUILD_SOFT_TIME_LIMIT
        < settings.GEOJSON_REBUILD_HARD_TIME_LIMIT
    )
