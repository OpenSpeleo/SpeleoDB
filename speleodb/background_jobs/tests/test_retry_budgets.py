"""Failures stop automatically; explicit operator retries remain possible."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from celery import current_app
from django.contrib import admin
from django.contrib.admin.models import CHANGE
from django.contrib.admin.models import LogEntry
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from speleodb.background_jobs.admin import BackgroundJobAdmin
from speleodb.background_jobs.models import BackgroundJob
from speleodb.background_jobs.models import JobArtifact
from speleodb.background_jobs.models import JobAttempt
from speleodb.background_jobs.models import JobState
from speleodb.background_jobs.services import claim_attempt
from speleodb.background_jobs.services import dispatch_attempt
from speleodb.background_jobs.services import dispatch_notification
from speleodb.background_jobs.services import request_export
from speleodb.background_jobs.services import request_notification
from speleodb.background_jobs.services import retry_cleanup
from speleodb.background_jobs.services import retry_delay
from speleodb.background_jobs.services import retry_export
from speleodb.background_jobs.storage import upload_archive
from speleodb.background_jobs.tasks import delete_expired_artifacts
from speleodb.background_jobs.tasks import maintain_background_jobs
from speleodb.background_jobs.tasks import send_export_notification
from speleodb.users.tests.factories import UserFactory
from speleodb.utils.s3_storages import ExportStorage

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from kombu.simple import SimpleQueue
    from pytest_django.fixtures import Settings

    from speleodb.users.models import User


@pytest.mark.usefixtures("unavailable_publication")
@pytest.mark.django_db
def test_final_publication_failure_requires_a_manual_new_cycle(
    user: User, settings: Settings
) -> None:
    now = timezone.now()
    job, _ = request_export(user)
    assert now <= job.created_at <= timezone.now()
    assert job.current_attempt_id is not None
    attempt = job.attempts.get(pk=job.current_attempt_id)
    assert now <= attempt.created_at <= timezone.now()
    assert attempt.dispatch_after == attempt.created_at
    # Start at the last durable attempt; do not manufacture preceding outages.
    attempt.cycle_attempt = settings.EXPORTS_MAX_ATTEMPTS
    attempt.save(update_fields=["cycle_attempt"])
    dispatch_attempt(attempt.pk)
    attempt.refresh_from_db()
    job.refresh_from_db()
    assert attempt.state == JobState.FAILED
    assert attempt.error == "Export publication failed; the broker is unavailable."
    assert attempt.finished_at is not None
    assert now <= attempt.finished_at <= timezone.now()
    assert job.state == JobState.FAILED
    assert job.next_attempt_at is None
    dispatch_attempt(attempt.pk)
    assert job.attempts.count() == 1
    now = timezone.now()
    retried = retry_export(job, user)
    assert retried.current_attempt_id is not None
    manual_attempt: JobAttempt = retried.attempts.get(pk=retried.current_attempt_id)
    assert manual_attempt.cycle_attempt == 1
    assert now <= manual_attempt.created_at <= timezone.now()
    assert manual_attempt.dispatch_after == manual_attempt.created_at


@pytest.mark.usefixtures("operation_queue")
@pytest.mark.django_db
def test_stale_publication_is_failed_without_republishing_the_same_attempt(
    user: User, settings: Settings
) -> None:
    now = timezone.now()
    job, _ = request_export(user)
    attempt = job.attempts.get()
    with (
        current_app.connection_for_write() as broker,
        broker.SimpleQueue("exports") as exports,
    ):
        exports.clear()
        try:
            dispatch_attempt(attempt.pk)
            assert exports.qsize() == 1
            attempt.refresh_from_db()
            assert attempt.dispatched_at is not None
            assert attempt.dispatch_started_at == attempt.dispatched_at
            assert now <= attempt.dispatched_at <= timezone.now()
            assert attempt.dispatch_after == attempt.dispatched_at + timedelta(
                seconds=settings.EXPORTS_DISPATCH_LEASE_SECONDS
            )
            dispatch_attempt(attempt.pk)
            assert exports.qsize() == 1
            attempt.refresh_from_db()
            assert attempt.state == JobState.QUEUED
            JobAttempt.objects.filter(pk=attempt.pk).update(
                dispatch_after=timezone.now() - timedelta(seconds=1)
            )
            dispatch_attempt(attempt.pk)
            assert exports.qsize() == 1
            attempt.refresh_from_db()
            job.refresh_from_db()
            assert attempt.state == JobState.FAILED
            assert "not claimed" in attempt.error
            assert job.state == JobState.RETRY_WAIT
            assert (
                claim_attempt(str(job.pk), str(attempt.pk), str(attempt.task_id))
                is None
            )
        finally:
            exports.clear()


@pytest.mark.usefixtures("unavailable_publication")
@pytest.mark.django_db
def test_final_notification_publication_failure_requires_manual_resend(
    user: User, settings: Settings
) -> None:
    job = BackgroundJob.objects.create(
        requester=user,
        state=JobState.FAILED,
        notification_due_at=timezone.now(),
        notification_attempts=settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS - 1,
    )
    dispatch_notification(job.pk)
    job.refresh_from_db()
    assert job.notification_attempts == settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS
    assert job.notification_error == "Notification publication failed."
    assert job.notification_state == "failed"
    assert job.notification_due_at is None
    dispatch_notification(job.pk)
    job.refresh_from_db()
    assert job.notification_attempts == settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS
    assert job.attempts.count() == 0
    request_notification(job, user)
    job.refresh_from_db()
    assert job.notification_attempts == 0
    assert job.notification_state == "pending"


@pytest.mark.django_db
def test_unclaimed_notifications_exhaust_the_same_finite_budget(
    user: User, settings: Settings, operation_queue: SimpleQueue
) -> None:
    settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS = 2
    now = timezone.now()
    job = BackgroundJob.objects.create(
        requester=user, state=JobState.FAILED, notification_due_at=now
    )
    dispatch_notification(job.pk)
    job.refresh_from_db()
    old_token = str(job.notification_token)
    maintain_background_jobs.run()
    assert operation_queue.qsize() == 1
    BackgroundJob.objects.filter(pk=job.pk).update(
        notification_due_at=timezone.now() - timedelta(seconds=1)
    )
    now = timezone.now()
    maintain_background_jobs.run()
    job.refresh_from_db()
    assert job.notification_state == "pending"
    assert job.notification_due_at is not None
    assert now + timedelta(seconds=60) <= job.notification_due_at
    assert job.notification_due_at <= timezone.now() + timedelta(seconds=60)
    BackgroundJob.objects.filter(pk=job.pk).update(notification_due_at=timezone.now())
    maintain_background_jobs.run()
    assert (
        send_export_notification.run(str(job.pk), old_token)["notification"]
        == "ignored"
    )
    BackgroundJob.objects.filter(pk=job.pk).update(
        notification_due_at=timezone.now() - timedelta(seconds=1)
    )
    now = timezone.now()
    maintain_background_jobs.run()
    job.refresh_from_db()
    assert job.notification_state == "failed"
    assert job.notification_due_at is None
    maintain_background_jobs.run()
    assert operation_queue.qsize() == settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS


def _cleanup_subject(
    user: User, now: datetime, *, published: bool
) -> tuple[BackgroundJob, JobAttempt]:
    state = JobState.READY if published else JobState.FAILED
    job = BackgroundJob.objects.create(requester=user, state=state)
    attempt = JobAttempt.objects.create(
        job=job,
        number=1,
        state=state,
        deadline_at=now - timedelta(minutes=6),
        object_key=f"exports/{uuid.uuid4()}.zip",
    )
    if published:
        JobArtifact.objects.create(
            job=job,
            attempt=attempt,
            object_key=attempt.object_key,
            filename="archive.zip",
            size_bytes=20,
            sha256="a" * 64,
            ready_at=now - timedelta(hours=25),
            expires_at=now - timedelta(hours=1),
        )
    return job, attempt


@pytest.mark.django_db
@pytest.mark.parametrize("published", [False, True])
def test_cleanup_exhaustion_retains_rows_and_admin_retry_is_audited(
    user: User, settings: Settings, tmp_path: Path, published: bool
) -> None:
    settings.EXPORTS_MAX_CLEANUP_ATTEMPTS = 5
    now = timezone.now()
    job, attempt = _cleanup_subject(user, now, published=published)
    archive = tmp_path / "archive.zip"
    archive.write_bytes(b"archive data")
    valid_key = attempt.object_key
    storage = ExportStorage()
    upload_archive(archive, key=valid_key, filename=archive.name, sha256="a" * 64)
    try:
        assert storage.exists(valid_key.removeprefix("exports/"))
        # The real deletion rejects a key outside the export namespace.
        attempt.object_key = f"outside-exports/{attempt.pk}.zip"
        attempt.save(update_fields=["object_key"])
        for number, delay in enumerate((60, 120, 240, 480, None), start=1):
            delete_expired_artifacts.run()
            attempt.refresh_from_db()
            assert attempt.cleanup_attempts == number
            assert attempt.object_deleted_at is None
            assert attempt.cleanup_error == "Deletion failed (ValueError)."
            delete_expired_artifacts.run()
            attempt.refresh_from_db()
            assert attempt.cleanup_attempts == number
            if delay is not None:
                assert attempt.cleanup_due_at is not None
                assert now + timedelta(seconds=delay) <= attempt.cleanup_due_at
                assert attempt.cleanup_due_at <= timezone.now() + timedelta(
                    seconds=delay
                )
                now = timezone.now()
                JobAttempt.objects.filter(pk=attempt.pk).update(cleanup_due_at=now)
            else:
                assert attempt.cleanup_due_at is None
        delete_expired_artifacts.run()
        attempt.refresh_from_db()
        assert attempt.cleanup_attempts == settings.EXPORTS_MAX_CLEANUP_ATTEMPTS
        assert BackgroundJob.objects.filter(pk=job.pk).exists()
        with pytest.raises(PermissionDenied):
            retry_cleanup(job, user)
        operator = UserFactory.create(is_staff=True)
        request = RequestFactory().post("/admin/background_jobs/backgroundjob/")
        request.user = operator
        model_admin = BackgroundJobAdmin(BackgroundJob, admin.site)
        SessionMiddleware(lambda _request: HttpResponse()).process_request(request)
        MessageMiddleware(lambda _request: HttpResponse()).process_request(request)
        model_admin.retry_cleanup(request, BackgroundJob.objects.filter(pk=job.pk))
        attempt.refresh_from_db()
        assert attempt.cleanup_attempts == 0
        assert attempt.cleanup_error == "Deletion failed (ValueError)."
        assert LogEntry.objects.filter(
            user=operator,
            object_id=str(job.pk),
            action_flag=CHANGE,
            change_message__contains="Reset cleanup retry budget",
        ).exists()
        attempt.object_key = valid_key
        attempt.save(update_fields=["object_key"])
        delete_expired_artifacts.run()
        attempt.refresh_from_db()
        assert attempt.object_deleted_at is not None
        assert now <= attempt.object_deleted_at <= timezone.now()
        assert attempt.cleanup_error == ""
        assert not storage.exists(valid_key.removeprefix("exports/"))
        if published:
            artifact = JobArtifact.objects.get(job=job)
            assert artifact.deleted_at is not None
            assert now <= artifact.deleted_at <= timezone.now()
            assert artifact.delete_error == ""
    finally:
        storage.delete_file(valid_key.removeprefix("exports/"))


@pytest.mark.django_db
def test_durable_retry_delay_reaches_and_keeps_its_cap(settings: Settings) -> None:
    settings.EXPORTS_RETRY_BASE_DELAY_SECONDS = 60
    settings.EXPORTS_RETRY_MAX_DELAY_SECONDS = 3600
    assert [retry_delay(number).total_seconds() for number in (1, 2, 6, 7, 8)] == [
        60,
        120,
        1920,
        3600,
        3600,
    ]
