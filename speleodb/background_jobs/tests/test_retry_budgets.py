"""Failures stop automatically; explicit operator retries remain possible."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from django.contrib import admin
from django.contrib.admin.models import CHANGE
from django.contrib.admin.models import LogEntry
from django.core.exceptions import PermissionDenied
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
from speleodb.background_jobs.services import retry_due_jobs
from speleodb.background_jobs.services import retry_export
from speleodb.background_jobs.tasks import delete_expired_artifacts
from speleodb.background_jobs.tasks import maintain_background_jobs
from speleodb.background_jobs.tasks import send_export_notification
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from datetime import datetime

    from pytest_django.fixtures import Settings

    from speleodb.users.models import User

pytestmark = pytest.mark.django_db


def test_failed_publications_consume_the_generation_cycle_budget(
    user: User, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.EXPORTS_MAX_ATTEMPTS = 3
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    publish = MagicMock(side_effect=ConnectionError("broker unavailable"))
    monkeypatch.setattr(
        "speleodb.background_jobs.services.current_app.send_task", publish
    )
    job, _ = request_export(user)
    for cycle, delay in ((1, 60), (2, 120), (3, None)):
        assert job.current_attempt_id is not None
        attempt = job.attempts.get(pk=job.current_attempt_id)
        dispatch_attempt(attempt.pk)
        attempt.refresh_from_db()
        job.refresh_from_db()
        assert attempt.state == JobState.FAILED
        assert attempt.cycle_attempt == cycle
        assert attempt.finished_at == now
        assert publish.call_count == cycle
        dispatch_attempt(attempt.pk)
        assert publish.call_count == cycle
        if delay is not None:
            assert job.state == JobState.RETRY_WAIT
            assert job.next_attempt_at == now + timedelta(seconds=delay)
            now += timedelta(seconds=delay)
            retry_due_jobs(now)
            job.refresh_from_db()
        else:
            assert job.state == JobState.FAILED
            assert job.next_attempt_at is None
    assert job.attempts.count() == settings.EXPORTS_MAX_ATTEMPTS
    retried = retry_export(job, user)
    assert retried.current_attempt_id is not None
    assert retried.attempts.get(pk=retried.current_attempt_id).cycle_attempt == 1


def test_stale_publication_is_failed_without_republishing_the_same_attempt(
    user: User, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    publish = MagicMock()
    monkeypatch.setattr(
        "speleodb.background_jobs.services.current_app.send_task", publish
    )
    job, _ = request_export(user)
    attempt = job.attempts.get()
    dispatch_attempt(attempt.pk)
    now += timedelta(seconds=settings.EXPORTS_DISPATCH_LEASE_SECONDS + 1)
    dispatch_attempt(attempt.pk)
    publish.assert_called_once()
    attempt.refresh_from_db()
    job.refresh_from_db()
    assert attempt.state == JobState.FAILED
    assert "not claimed" in attempt.error
    assert job.state == JobState.RETRY_WAIT
    assert claim_attempt(str(job.pk), str(attempt.pk), str(attempt.task_id)) is None


def test_publication_error_cannot_fail_an_already_claimed_worker(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    job, _ = request_export(user)
    attempt = job.attempts.get()

    def accepted_then_connection_lost(*_args: object, **_kwargs: object) -> None:
        assert (
            claim_attempt(str(job.pk), str(attempt.pk), str(attempt.task_id))
            is not None
        )
        raise ConnectionError("broker confirmation lost")

    monkeypatch.setattr(
        "speleodb.background_jobs.services.current_app.send_task",
        accepted_then_connection_lost,
    )
    dispatch_attempt(attempt.pk)
    job.refresh_from_db()
    attempt.refresh_from_db()
    assert job.state == JobState.RUNNING
    assert attempt.state == JobState.RUNNING


def test_notification_publication_and_delivery_share_one_budget(
    user: User, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS = 3
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    publish = MagicMock(
        side_effect=[ConnectionError("offline"), None, ConnectionError()]
    )
    monkeypatch.setattr(
        "speleodb.background_jobs.services.current_app.send_task", publish
    )
    job = BackgroundJob.objects.create(
        requester=user, state=JobState.FAILED, notification_due_at=now
    )
    dispatch_notification(job.pk)
    job.refresh_from_db()
    assert job.notification_attempts == 1
    assert job.notification_due_at == now + timedelta(seconds=60)
    now += timedelta(seconds=60)
    dispatch_notification(job.pk)
    job.refresh_from_db()
    assert job.notification_state == "queued"
    assert job.notification_token is not None
    token = str(job.notification_token)
    # No verified email: delivery fails, but publication already consumed this try.
    result = send_export_notification.run(str(job.pk), token)
    job.refresh_from_db()
    assert result["notification"] == "pending"
    assert job.notification_attempts == 2  # noqa: PLR2004
    assert job.notification_due_at == now + timedelta(seconds=120)
    assert send_export_notification.run(str(job.pk), token)["notification"] == "ignored"
    now += timedelta(seconds=120)
    dispatch_notification(job.pk)
    job.refresh_from_db()
    assert job.notification_state == "failed"
    assert job.notification_attempts == settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS
    assert job.notification_due_at is None
    dispatch_notification(job.pk)
    assert publish.call_count == settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS
    assert job.attempts.count() == 0
    request_notification(job, user)
    job.refresh_from_db()
    assert job.notification_attempts == 0
    assert job.notification_state == "pending"


def test_unclaimed_notifications_exhaust_the_same_finite_budget(
    user: User, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS = 2
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    publish = MagicMock()
    monkeypatch.setattr(
        "speleodb.background_jobs.services.current_app.send_task", publish
    )
    job = BackgroundJob.objects.create(
        requester=user, state=JobState.FAILED, notification_due_at=now
    )
    dispatch_notification(job.pk)
    job.refresh_from_db()
    old_token = str(job.notification_token)
    maintain_background_jobs.run()
    publish.assert_called_once()
    now += timedelta(seconds=settings.EXPORTS_DISPATCH_LEASE_SECONDS + 1)
    maintain_background_jobs.run()
    job.refresh_from_db()
    assert job.notification_state == "pending"
    assert job.notification_due_at == now + timedelta(seconds=60)
    now += timedelta(seconds=60)
    maintain_background_jobs.run()
    assert (
        send_export_notification.run(str(job.pk), old_token)["notification"]
        == "ignored"
    )
    now += timedelta(seconds=settings.EXPORTS_DISPATCH_LEASE_SECONDS + 1)
    maintain_background_jobs.run()
    job.refresh_from_db()
    assert job.notification_state == "failed"
    assert job.notification_due_at is None
    maintain_background_jobs.run()
    assert publish.call_count == settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS


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
        object_version="version-1",
    )
    if published:
        JobArtifact.objects.create(
            job=job,
            attempt=attempt,
            object_key=attempt.object_key,
            object_version=attempt.object_version,
            filename="archive.zip",
            size_bytes=20,
            sha256="a" * 64,
            ready_at=now - timedelta(hours=25),
            expires_at=now - timedelta(hours=1),
        )
    return job, attempt


@pytest.mark.parametrize("published", [False, True])
def test_cleanup_exhaustion_retains_rows_and_admin_retry_is_audited(
    user: User, settings: Settings, monkeypatch: pytest.MonkeyPatch, published: bool
) -> None:
    settings.EXPORTS_MAX_CLEANUP_ATTEMPTS = 5
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    job, attempt = _cleanup_subject(user, now, published=published)
    delete = MagicMock(side_effect=OSError("sensitive provider response"))
    monkeypatch.setattr("speleodb.background_jobs.tasks.delete_archive", delete)
    for number, delay in enumerate((60, 120, 240, 480, None), start=1):
        delete_expired_artifacts.run()
        attempt.refresh_from_db()
        assert attempt.cleanup_attempts == number
        assert attempt.object_deleted_at is None
        assert attempt.cleanup_error == "Deletion failed (OSError)."
        assert delete.call_count == number
        delete_expired_artifacts.run()
        assert delete.call_count == number
        if delay is not None:
            assert attempt.cleanup_due_at == now + timedelta(seconds=delay)
            now += timedelta(seconds=delay)
        else:
            assert attempt.cleanup_due_at is None
    now += timedelta(days=91)
    delete_expired_artifacts.run()
    assert delete.call_count == settings.EXPORTS_MAX_CLEANUP_ATTEMPTS
    assert BackgroundJob.objects.filter(pk=job.pk).exists()
    with pytest.raises(PermissionDenied):
        retry_cleanup(job, user)
    operator = UserFactory.create(is_staff=True)
    request = RequestFactory().post("/admin/background_jobs/backgroundjob/")
    request.user = operator
    model_admin = BackgroundJobAdmin(BackgroundJob, admin.site)
    monkeypatch.setattr(model_admin, "message_user", MagicMock())
    model_admin.retry_cleanup(request, BackgroundJob.objects.filter(pk=job.pk))
    attempt.refresh_from_db()
    assert attempt.cleanup_attempts == 0
    assert attempt.cleanup_error == "Deletion failed (OSError)."
    assert LogEntry.objects.filter(
        user=operator,
        object_id=str(job.pk),
        action_flag=CHANGE,
        change_message__contains="Reset cleanup retry budget",
    ).exists()
    delete.side_effect = None
    delete_expired_artifacts.run()
    attempt.refresh_from_db()
    assert attempt.object_deleted_at == now
    assert attempt.cleanup_error == ""
    if published:
        artifact = JobArtifact.objects.get(job=job)
        assert artifact.deleted_at == now
        assert artifact.delete_error == ""


class SimulatedWorkerExit(BaseException):
    """A process exit bypasses ordinary dependency exception handling."""


def test_cleanup_process_losses_are_counted_and_require_manual_recovery(
    user: User, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.EXPORTS_MAX_CLEANUP_ATTEMPTS = 2
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    job, attempt = _cleanup_subject(user, now, published=False)
    delete = MagicMock(side_effect=SimulatedWorkerExit())
    monkeypatch.setattr("speleodb.background_jobs.tasks.delete_archive", delete)
    for number in range(1, settings.EXPORTS_MAX_CLEANUP_ATTEMPTS + 1):
        with pytest.raises(SimulatedWorkerExit):
            delete_expired_artifacts.run()
        attempt.refresh_from_db()
        assert attempt.cleanup_attempts == number
        assert attempt.cleanup_error == "Object deletion has not been confirmed."
        delay = 60 if number == 1 else 120
        assert attempt.cleanup_due_at == now + timedelta(
            seconds=settings.EXPORTS_CLEANUP_LEASE_SECONDS + delay
        )
        now += timedelta(seconds=settings.EXPORTS_CLEANUP_LEASE_SECONDS + delay + 1)
    delete_expired_artifacts.run()
    assert delete.call_count == settings.EXPORTS_MAX_CLEANUP_ATTEMPTS
    assert retry_cleanup(job, UserFactory.create(is_staff=True)) == 1
    attempt.refresh_from_db()
    assert attempt.cleanup_attempts == 0
    assert attempt.cleanup_token is None


def test_stale_cleanup_completion_cannot_overwrite_a_new_claim(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = timezone.now()
    _job, attempt = _cleanup_subject(user, now, published=False)
    newer_token = uuid.uuid4()

    def superseded_delete(**_kwargs: str) -> None:
        JobAttempt.objects.filter(pk=attempt.pk).update(
            cleanup_token=newer_token,
            cleanup_error="A newer cleanup owns this object.",
        )
        raise OSError("late error")

    monkeypatch.setattr(
        "speleodb.background_jobs.tasks.delete_archive", superseded_delete
    )
    delete_expired_artifacts.run()
    attempt.refresh_from_db()
    assert attempt.cleanup_token == newer_token
    assert attempt.cleanup_error == "A newer cleanup owns this object."
    assert attempt.object_deleted_at is None


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
