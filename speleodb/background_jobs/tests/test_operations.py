"""Scheduling receipts distinguish execution from uncertain broker submission."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any
from unittest.mock import patch

import pytest
from celery import current_app
from celery.app.task import Context
from django.contrib.admin.models import LogEntry
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.db import connection
from django.db import transaction
from django_celery_results.models import TaskResult
from kombu.exceptions import OperationalError

from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.background_jobs.operation_execution import operation_execution
from speleodb.background_jobs.operations import TASK_NAMES
from speleodb.background_jobs.operations import _publish
from speleodb.background_jobs.operations import get_operation_parameters
from speleodb.background_jobs.operations import receipt_task_ids
from speleodb.background_jobs.operations import schedule_operation
from speleodb.common.enums import ProjectType
from speleodb.common.enums import TaskResultStatus
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from pathlib import Path

    from kombu.simple import SimpleQueue
    from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks

    from speleodb.surveys.models import Project
    from speleodb.users.models import User


@pytest.mark.usefixtures("operation_queue")
@pytest.mark.django_db
def test_publication_waits_for_commit_and_records_parameters(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    operation_queue: SimpleQueue,
) -> None:
    user: User = UserFactory.create(is_superuser=True)
    project: Project = ProjectFactory.create(type=ProjectType.ARIANE)
    with django_capture_on_commit_callbacks(execute=True):
        receipt = schedule_operation("project", requester=user, project_id=project.pk)
        result = TaskResult.objects.get(task_id=receipt.task_ids[0])
        assert result.status == TaskResultStatus.PENDING
        assert json.loads(result.meta)["publication"] == "unattempted"
        assert operation_queue.qsize() == 0
    result.refresh_from_db()
    assert json.loads(result.meta)["publication"] == "confirmed"
    assert get_operation_parameters(result) == {
        "operation": "project",
        "project_id": str(project.pk),
        "force": False,
    }
    message = operation_queue.get(block=False)
    assert message.headers["id"] == result.task_id
    metadata: object = message.headers["meta"]
    assert isinstance(metadata, dict)
    assert metadata["publication"] == "confirmed"
    message.ack()
    _publish(receipt.task_ids)
    assert operation_queue.qsize() == 0


@pytest.mark.usefixtures("operation_queue")
@pytest.mark.django_db
def test_batch_records_independent_tasks_and_partial_publication(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    operation_queue: SimpleQueue,
) -> None:
    user: User = UserFactory.create(is_superuser=True)
    projects = [ProjectFactory.create(type=ProjectType.COMPASS) for _ in range(3)]
    ProjectFactory.create(type=ProjectType.ARIANE, exclude_geojson=True)
    ProjectFactory.create(type=ProjectType.OTHER)
    publish = current_app.send_task
    calls = 0

    def publish_until_failure(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        # Keep successful publication real; fail only the selected broker call.
        if calls > 1:
            raise OperationalError("broker unavailable")
        return publish(*args, **kwargs)

    with (
        patch(
            "speleodb.background_jobs.operations.current_app.send_task",
            new=publish_until_failure,
        ),
        django_capture_on_commit_callbacks(execute=True),
    ):
        receipt = schedule_operation("all", requester=user)
    assert len(receipt.task_ids) == len(projects)
    assert calls == operation_queue.qsize() + 1
    assert operation_queue.qsize() == 1
    assert receipt.group_id is not None
    assert receipt_task_ids(receipt.group_id) == receipt.task_ids
    assert [
        json.loads(TaskResult.objects.get(task_id=task_id).meta)["publication"]
        for task_id in receipt.task_ids
    ] == ["confirmed", "ambiguous", "unattempted"]


@pytest.mark.usefixtures("operation_queue")
@pytest.mark.django_db
def test_rerun_is_new_execution_and_keeps_force(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    user: User = UserFactory.create(is_superuser=True)
    project: Project = ProjectFactory.create(type=ProjectType.ARIANE)
    with django_capture_on_commit_callbacks(execute=True):
        first = schedule_operation(
            "project", requester=user, project_id=project.pk, force=True
        )
        row = TaskResult.objects.get(task_id=first.task_ids[0])
        second = schedule_operation(requester=user, **get_operation_parameters(row))
    assert first.task_ids != second.task_ids
    assert (
        get_operation_parameters(TaskResult.objects.get(task_id=second.task_ids[0]))[
            "force"
        ]
        is True
    )


@pytest.mark.usefixtures("operation_queue")
@pytest.mark.django_db
def test_duplicate_delivery_cannot_claim_started_or_completed_execution() -> None:
    result = TaskResult.objects.create(
        task_id="duplicate", task_name="operations", meta="{}"
    )
    with operation_execution(result.task_id) as execution:
        assert execution is not None
        with operation_execution(result.task_id) as duplicate:
            assert duplicate is None
        execution.complete({"generated": 1})
    with operation_execution(result.task_id) as duplicate:
        assert duplicate is None
    result.refresh_from_db()
    assert result.status == TaskResultStatus.SUCCESS
    assert json.loads(result.result) == {"generated": 1}


@pytest.mark.usefixtures("operation_queue")
@pytest.mark.django_db
@pytest.mark.parametrize(("active", "superuser"), [(True, False), (False, True)])
def test_scheduling_requires_active_superuser(active: bool, superuser: bool) -> None:
    user: User = UserFactory.create(is_active=active, is_superuser=superuser)
    with pytest.raises(PermissionDenied):
        schedule_operation("all", requester=user)
    assert not TaskResult.objects.exists()


@pytest.mark.usefixtures("operation_queue")
@pytest.mark.django_db
def test_preexecution_failure_keeps_published_operation_parameters(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    operation_queue: SimpleQueue,
) -> None:
    user: User = UserFactory.create(is_superuser=True)
    project: Project = ProjectFactory.create(type=ProjectType.ARIANE)
    with django_capture_on_commit_callbacks(execute=True):
        receipt = schedule_operation("project", requester=user, project_id=project.pk)
    message = operation_queue.get(block=False)
    metadata = message.headers["meta"]
    message.ack()
    request = Context(
        task=TASK_NAMES["project"],
        args=(str(project.pk),),
        meta=metadata,
    )
    # Exercise Celery's real failure storage before the task body has entered.
    current_app.backend.mark_as_failure(
        receipt.task_ids[0],
        TypeError("Task signature rejected"),
        request=request,
    )
    result = TaskResult.objects.get(task_id=receipt.task_ids[0])
    assert result.status == TaskResultStatus.FAILURE
    assert get_operation_parameters(result)["project_id"] == str(project.pk)
    assert json.loads(result.meta)["publication"] == "confirmed"


@pytest.mark.usefixtures("operation_queue")
@pytest.mark.django_db
def test_rolled_back_submission_never_publishes(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    operation_queue: SimpleQueue,
) -> None:
    user: User = UserFactory.create(is_superuser=True)
    project: Project = ProjectFactory.create(type=ProjectType.ARIANE)

    def submit_then_roll_back() -> None:
        with transaction.atomic():
            schedule_operation("project", requester=user, project_id=project.pk)
            raise RuntimeError("request rolled back")

    with (
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(RuntimeError, match="request rolled back"),
    ):
        submit_then_roll_back()
    assert operation_queue.qsize() == 0
    assert not TaskResult.objects.exists()


@pytest.mark.usefixtures("operation_queue")
@pytest.mark.django_db
def test_execution_outcome_is_audited(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    user: User = UserFactory.create(is_superuser=True)
    project: Project = ProjectFactory.create(type=ProjectType.ARIANE)
    with django_capture_on_commit_callbacks(execute=True):
        receipt = schedule_operation("project", requester=user, project_id=project.pk)
    with operation_execution(receipt.task_ids[0]) as execution:
        assert execution is not None
        execution.complete({"processed": 1, "generated": 1})
    audit = LogEntry.objects.filter(user=user, object_id=str(project.pk)).latest(
        "action_time"
    )
    assert json.loads(audit.change_message)["stage"] == "completed"
    assert json.loads(audit.change_message)["summary"]["generated"] == 1


@pytest.mark.usefixtures("operation_queue")
@pytest.mark.django_db
def test_terminal_failure_always_contains_a_celery_decodable_exception() -> None:
    result = TaskResult.objects.create(
        task_id="failure-result",
        task_name="operations",
        meta="{}",
        content_type="application/json",
        content_encoding="utf-8",
    )
    with (
        pytest.raises(ValueError, match="conversion refused"),
        operation_execution(result.task_id),
    ):
        raise ValueError("conversion refused")
    result.refresh_from_db()
    assert result.status == TaskResultStatus.FAILURE
    error = current_app.backend.exception_to_python(json.loads(result.result))
    assert isinstance(error, ValueError)
    assert str(error) == "conversion refused"


@pytest.mark.usefixtures("operation_queue")
@pytest.mark.django_db(transaction=True)
def test_deleted_requester_audit_failure_preserves_operation_exception(
    tmp_path: Path,
) -> None:
    assert connection.vendor == "postgresql"
    user: User = UserFactory.create(is_superuser=True)
    project: Project = ProjectFactory.create(type=ProjectType.ARIANE)
    receipt = schedule_operation("project", requester=user, project_id=project.pk)
    user.delete()
    missing_source = tmp_path / "missing-survey"
    with (
        pytest.raises(FileNotFoundError) as raised,
        operation_execution(receipt.task_ids[0]),
    ):
        missing_source.read_bytes()
    assert raised.value.filename == str(missing_source)
    result = TaskResult.objects.get(task_id=receipt.task_ids[0])
    assert result.status == TaskResultStatus.FAILURE
    assert json.loads(result.meta)["stage"] == "failed"
    error = current_app.backend.exception_to_python(json.loads(result.result))
    assert isinstance(error, FileNotFoundError)
    assert error.args == raised.value.args


@pytest.mark.usefixtures("operation_queue")
@pytest.mark.django_db
def test_postcommit_database_failure_does_not_escape_scheduling(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    operation_queue: SimpleQueue,
) -> None:
    user: User = UserFactory.create(is_superuser=True)
    project: Project = ProjectFactory.create(type=ProjectType.ARIANE)
    with (
        # Isolate database failure without disconnecting the shared test server.
        patch(
            "speleodb.background_jobs.operations.TaskResult.objects.get",
            side_effect=DatabaseError("Result database unavailable"),
        ),
        django_capture_on_commit_callbacks(execute=True),
    ):
        receipt = schedule_operation("project", requester=user, project_id=project.pk)
    assert operation_queue.qsize() == 0
    result = TaskResult.objects.get(task_id=receipt.task_ids[0])
    assert result.status == TaskResultStatus.PENDING
    assert json.loads(result.meta)["publication"] == "unattempted"
