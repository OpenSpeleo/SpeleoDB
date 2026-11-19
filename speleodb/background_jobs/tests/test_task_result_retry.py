"""Manual task retries requeue the same execution without a confirmation page."""

from __future__ import annotations

import ast
import json
from http import HTTPStatus
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from celery import current_app
from django.test import Client
from django.urls import reverse
from django_celery_results.models import TaskResult

from speleodb.background_jobs.dispatch import dispatch_task
from speleodb.background_jobs.models import JobState
from speleodb.background_jobs.operations import TASK_NAMES
from speleodb.background_jobs.services import request_export
from speleodb.background_jobs.storage import delete_archive
from speleodb.background_jobs.tasks import generate_export
from speleodb.background_jobs.tasks import send_export_notification
from speleodb.common.enums import TaskResultStatus
from speleodb.surveys.tasks import refresh_project_geojson
from speleodb.surveys.tasks import reset_project_history
from speleodb.users.models import LogEntry
from speleodb.users.tests.factories import VerifiedUserFactory

if TYPE_CHECKING:
    from pathlib import Path

    from kombu.simple import SimpleQueue
    from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
    from pytest_django.fixtures import Settings

    from speleodb.users.models import User


@pytest.fixture
def failed_result(operation_queue: SimpleQueue) -> TaskResult:
    return _failed_project_result()


def _failed_project_result(operation: str = "project") -> TaskResult:
    # A real missing project fails in the actual worker task, including the
    # execution guard and Celery's backend serialization of args and metadata.
    current_app.conf.update(task_store_eager_result=True)
    project_id = str(uuid4())
    result = TaskResult.objects.create(
        task_id=str(uuid4()),
        task_name=TASK_NAMES[operation],
        status=TaskResultStatus.PENDING,
        content_type="application/json",
        content_encoding="utf-8",
        task_args=json.dumps([project_id]),
        task_kwargs=json.dumps(
            {"force_recompute": True} if operation == "project" else {}
        ),
        meta=json.dumps(
            {"operation": operation, "project_id": project_id, "force": True}
        ),
    )
    task = reset_project_history if operation == "history" else refresh_project_geojson
    execution = task.apply(
        args=(project_id,),
        kwargs={"force_recompute": True} if operation == "project" else {},
        task_id=result.task_id,
        throw=False,
    )
    assert execution.failed()
    result.refresh_from_db()
    assert result.status == TaskResultStatus.FAILURE
    return result


@pytest.mark.django_db
def test_failed_task_detail_and_list_offer_retry(
    admin_client: Client, staff_client: Client, failed_result: TaskResult
) -> None:
    detail = reverse(
        "admin:django_celery_results_taskresult_change", args=[failed_result.pk]
    )
    listing = reverse("admin:django_celery_results_taskresult_changelist")
    assert (
        'name="action" value="retry_failed"'
        in admin_client.get(detail).content.decode()
    )
    assert '<option value="retry_failed">RETRY selected failed tasks</option>' in (
        admin_client.get(listing).content.decode()
    )
    assert 'value="retry_failed"' not in staff_client.get(detail).content.decode()
    assert 'value="retry_failed"' not in staff_client.get(listing).content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("extended_repr", [False, True])
def test_retry_immediately_requeues_the_same_task(  # noqa: PLR0917 - Explicit pytest fixtures.
    admin_client: Client,
    admin_user: User,
    failed_result: TaskResult,
    operation_queue: SimpleQueue,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    extended_repr: bool,
) -> None:
    if extended_repr:
        failed_result.task_args = json.dumps(
            repr(tuple(json.loads(failed_result.task_args)))
        )
        failed_result.task_kwargs = json.dumps(
            repr(json.loads(failed_result.task_kwargs))
        )
        failed_result.save(update_fields=["task_args", "task_kwargs"])
    listing = reverse("admin:django_celery_results_taskresult_changelist")
    data = {"action": "retry_failed", "_selected_action": str(failed_result.pk)}
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(listing, data)
    assert response.status_code == HTTPStatus.FOUND
    assert TaskResult.objects.count() == 1
    retried = TaskResult.objects.get(pk=failed_result.pk)
    assert retried.task_id == failed_result.task_id
    assert retried.task_name == failed_result.task_name
    assert retried.status == TaskResultStatus.PENDING
    assert json.loads(retried.task_kwargs) == {"force_recompute": True}
    assert json.loads(retried.meta)["requester_id"] == str(admin_user.pk)
    assert "summary" not in json.loads(retried.meta)
    assert retried.traceback is None
    assert retried.result is None
    assert (
        TaskResult.objects.values_list("date_started", flat=True).get(pk=retried.pk)
        is None
    )
    message = operation_queue.get(block=False)
    assert message.headers["id"] == retried.task_id
    assert message.headers["task"] == retried.task_name
    assert message.payload[1] == {"force_recompute": True}
    message.ack()
    assert operation_queue.qsize() == 0
    audit = LogEntry.objects.get(actor_email=admin_user.email)
    assert audit.details["task_ids"] == [retried.task_id]
    admin_client.post(listing, data)
    assert operation_queue.qsize() == 0
    assert TaskResult.objects.count() == 1
    assert LogEntry.objects.count() == 1


@pytest.mark.django_db
def test_bulk_retry_skips_success_and_running_tasks(
    admin_client: Client,
    failed_result: TaskResult,
    operation_queue: SimpleQueue,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    other_failure = _failed_project_result()
    others = [
        TaskResult.objects.create(task_id=str(uuid4()), status=state)
        for state in (TaskResultStatus.SUCCESS, TaskResultStatus.STARTED)
    ]
    selected = [failed_result, other_failure, *others]
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(
            reverse("admin:django_celery_results_taskresult_changelist"),
            {
                "action": "retry_failed",
                "_selected_action": [str(row.pk) for row in selected],
            },
        )
    assert response.status_code == HTTPStatus.FOUND
    assert operation_queue.qsize() == len([failed_result, other_failure])
    assert TaskResult.objects.count() == len(selected)
    assert {
        task_id
        for details in LogEntry.objects.values_list("details", flat=True)
        for task_id in details["task_ids"]
    } == {failed_result.task_id, other_failure.task_id}
    for result in others:
        detail = admin_client.get(
            reverse("admin:django_celery_results_taskresult_change", args=[result.pk])
        )
        assert 'value="retry_failed"' not in detail.content.decode()


@pytest.mark.django_db
def test_retry_requires_superuser_and_csrf(
    admin_user: User,
    staff_client: Client,
    failed_result: TaskResult,
    operation_queue: SimpleQueue,
) -> None:
    listing = reverse("admin:django_celery_results_taskresult_changelist")
    data = {
        "action": "retry_failed",
        "_selected_action": str(failed_result.pk),
    }
    staff_client.post(listing, data)
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)
    assert csrf_client.post(listing, data).status_code == HTTPStatus.FORBIDDEN
    assert TaskResult.objects.count() == 1
    assert operation_queue.qsize() == 0
    assert not LogEntry.objects.exists()


@pytest.mark.django_db
def test_history_retry_is_immediate_and_keeps_task_identity(
    admin_client: Client,
    operation_queue: SimpleQueue,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    result = _failed_project_result("history")
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(
            reverse("admin:django_celery_results_taskresult_changelist"),
            {"action": "retry_failed", "_selected_action": str(result.pk)},
        )
    assert response.status_code == HTTPStatus.FOUND
    assert TaskResult.objects.get().task_id == result.task_id
    assert operation_queue.qsize() == 1


@pytest.mark.django_db
def test_unavailable_arguments_are_reported_without_executing_code(
    admin_client: Client,
    failed_result: TaskResult,
    operation_queue: SimpleQueue,
    tmp_path: Path,
) -> None:
    marker = tmp_path / "must-not-exist"
    failed_result.task_args = json.dumps(
        f"__import__('pathlib').Path({str(marker)!r}).touch()"
    )
    failed_result.save(update_fields=["task_args"])
    response = admin_client.post(
        reverse("admin:django_celery_results_taskresult_changelist"),
        {
            "action": "retry_failed",
            "_selected_action": str(failed_result.pk),
        },
        follow=True,
    )
    assert "arguments are unavailable" in response.content.decode()
    assert not marker.exists()
    assert operation_queue.qsize() == 0
    assert TaskResult.objects.count() == 1


@pytest.mark.django_db
def test_retry_does_not_allow_changing_result_fields(
    admin_client: Client, failed_result: TaskResult
) -> None:
    response = admin_client.post(
        reverse(
            "admin:django_celery_results_taskresult_change", args=[failed_result.pk]
        ),
        {"status": TaskResultStatus.SUCCESS},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    failed_result.refresh_from_db()
    assert failed_result.status == TaskResultStatus.FAILURE


def test_publication_preserves_full_arguments_for_exact_retries(
    operation_queue: SimpleQueue,
) -> None:
    args = [{"email_template_source": "campaign template " * 128}]
    kwargs = {"email": "recipient@example.test"}
    dispatch_task(
        "speleodb.campaigns.tasks.send_campaign_email",
        args=args,
        kwargs=kwargs,
        queue="background_control",
    )
    message = operation_queue.get(block=False)
    assert ast.literal_eval(message.headers["argsrepr"]) == args
    assert ast.literal_eval(message.headers["kwargsrepr"]) == kwargs
    message.ack()


@pytest.mark.django_db
def test_failed_export_retry_reuses_task_and_domain_attempt(
    admin_client: Client,
    operation_queue: SimpleQueue,
    settings: Settings,
    tmp_path: Path,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    # Exercise an actual filesystem failure before archive creation; no broker,
    # storage service or retry result is replaced.
    current_app.conf.update(task_store_eager_result=True)
    scratch_file = tmp_path / "not-a-directory"
    scratch_file.write_text("occupied")
    settings.EXPORTS_SCRATCH_DIR = str(scratch_file)
    settings.EXPORTS_MAX_ATTEMPTS = 1
    owner = VerifiedUserFactory.create()
    job, _ = request_export(owner)
    attempt = job.attempts.get()
    execution = generate_export.apply(
        args=(str(job.pk), str(attempt.pk)), task_id=str(attempt.task_id), throw=False
    )
    assert execution.failed()
    job.refresh_from_db()
    assert job.state == JobState.FAILED
    result = TaskResult.objects.get(task_id=str(attempt.task_id))
    assert result.status == TaskResultStatus.FAILURE
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(
            reverse("admin:django_celery_results_taskresult_changelist"),
            {
                "action": "retry_failed",
                "_selected_action": str(result.pk),
            },
        )
    assert response.status_code == HTTPStatus.FOUND
    job.refresh_from_db()
    assert job.attempts.count() == 1
    assert job.current_attempt_id == attempt.pk
    assert job.state == JobState.QUEUED
    result.refresh_from_db()
    assert TaskResult.objects.count() == 1
    assert result.status == TaskResultStatus.PENDING
    with (
        generate_export.app.connection_for_write() as broker,
        broker.SimpleQueue("exports") as queue,
    ):
        message = queue.get(block=False)
        assert message.headers["id"] == str(attempt.task_id)
        retry_args = tuple(message.payload[0])
        message.ack()
    settings.EXPORTS_SCRATCH_DIR = str(tmp_path / "working-scratch")
    try:
        retried = generate_export.apply(
            args=retry_args, task_id=str(attempt.task_id), throw=False
        )
        assert retried.successful()
        result.refresh_from_db()
        job.refresh_from_db()
        assert result.status == TaskResultStatus.SUCCESS
        assert job.state == JobState.READY
        assert TaskResult.objects.get().pk == result.pk
        assert job.attempts.get().task_id == attempt.task_id
    finally:
        attempt.refresh_from_db()
        if attempt.object_key:
            delete_archive(key=attempt.object_key)


@pytest.mark.django_db
def test_notification_retry_claims_same_task_before_publication(
    admin_client: Client,
    operation_queue: SimpleQueue,
    settings: Settings,
    tmp_path: Path,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    current_app.conf.update(task_store_eager_result=True)
    scratch_file = tmp_path / "not-a-directory"
    scratch_file.write_text("occupied")
    settings.EXPORTS_SCRATCH_DIR = str(scratch_file)
    settings.EXPORTS_MAX_ATTEMPTS = 1
    job, _ = request_export(VerifiedUserFactory.create())
    attempt = job.attempts.get()
    export_execution = generate_export.apply(
        args=(str(job.pk), str(attempt.pk)), task_id=str(attempt.task_id), throw=False
    )
    assert export_execution.failed()
    # Invalid token input exercises the notification task's real UUID failure.
    task_id = str(uuid4())
    execution = send_export_notification.apply(
        args=(str(job.pk), "invalid-token"), task_id=task_id, throw=False
    )
    assert execution.failed()
    result = TaskResult.objects.get(task_id=task_id)
    assert result.status == TaskResultStatus.FAILURE
    result_count = TaskResult.objects.count()
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(
            reverse("admin:django_celery_results_taskresult_changelist"),
            {"action": "retry_failed", "_selected_action": str(result.pk)},
        )
        assert response.status_code == HTTPStatus.FOUND
        job.refresh_from_db()
        assert job.notification_state == "queued"
        assert job.notification_token is not None
        assert operation_queue.qsize() == 0
        result.refresh_from_db()
        assert result.status == TaskResultStatus.PENDING
    message = operation_queue.get(block=False)
    assert message.headers["id"] == task_id
    assert message.payload[0] == [str(job.pk), str(job.notification_token)]
    message.ack()
    assert operation_queue.qsize() == 0
    assert TaskResult.objects.count() == result_count
