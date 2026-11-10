"""Workerless staging retains archive, notification and task-result behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from celery import current_app
from django.core import mail
from django_celery_results.models import TaskResult

from speleodb.background_jobs.models import JobArtifact
from speleodb.background_jobs.models import JobState
from speleodb.background_jobs.services import dispatch_notification
from speleodb.background_jobs.services import request_export
from speleodb.background_jobs.storage import delete_archive
from speleodb.background_jobs.tasks import send_export_notification
from speleodb.common.enums import TaskResultStatus
from speleodb.users.tests.factories import VerifiedUserFactory

if TYPE_CHECKING:
    from kombu.simple import SimpleQueue
    from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks

    from speleodb.users.models import User

MAX_FIXTURE_BYTES: int = 100_000


@pytest.mark.django_db
def test_immediate_export_and_notification_dispatch_complete(
    operation_queue: SimpleQueue,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    user: User = VerifiedUserFactory.create()
    current_app.conf.update(
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=False,
        CELERY_TASK_STORE_EAGER_RESULT=True,
    )
    with django_capture_on_commit_callbacks(execute=True):
        job, created = request_export(user)
    attempt = job.attempts.get()
    try:
        assert created
        job.refresh_from_db()
        assert job.state == JobState.READY
        artifact = JobArtifact.objects.get(job=job)
        assert artifact.size_bytes <= MAX_FIXTURE_BYTES
        dispatch_notification(job.pk)
        job.refresh_from_db()
        assert job.notification_state == "sent"
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user.email]
        assert TaskResult.objects.get(task_id=str(attempt.task_id)).status == (
            TaskResultStatus.SUCCESS
        )
        assert (
            TaskResult.objects.get(task_name=send_export_notification.name).status
            == TaskResultStatus.SUCCESS
        )
        assert operation_queue.qsize() == 0
        with (
            current_app.connection_for_write() as broker,
            broker.SimpleQueue("exports") as queue,
        ):
            assert queue.qsize() == 0
    finally:
        if attempt.object_key:
            delete_archive(key=attempt.object_key)
