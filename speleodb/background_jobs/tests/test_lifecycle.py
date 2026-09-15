"""Verify durable lifecycle transitions against actual database constraints."""

from __future__ import annotations

import os
import socket
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from allauth.account.models import EmailAddress
from celery.exceptions import Ignore
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMultiAlternatives
from django.core.management import call_command
from django.db import IntegrityError
from django.db import transaction
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
from django_celery_results.models import TaskResult

from speleodb.background_jobs.models import BackgroundJob
from speleodb.background_jobs.models import JobArtifact
from speleodb.background_jobs.models import JobAttempt
from speleodb.background_jobs.models import JobState
from speleodb.background_jobs.services import ExportConflictError
from speleodb.background_jobs.services import ExportExpiredError
from speleodb.background_jobs.services import ExportUnavailableError
from speleodb.background_jobs.services import artifact_download_url
from speleodb.background_jobs.services import claim_attempt
from speleodb.background_jobs.services import fail_attempt
from speleodb.background_jobs.services import publish_artifact
from speleodb.background_jobs.services import request_export
from speleodb.background_jobs.services import request_notification
from speleodb.background_jobs.services import retry_due_jobs
from speleodb.background_jobs.services import retry_export
from speleodb.background_jobs.tasks import _clean_scratch
from speleodb.background_jobs.tasks import generate_export
from speleodb.background_jobs.tasks import maintain_background_jobs
from speleodb.background_jobs.tasks import send_export_notification
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import Settings

    from speleodb.users.models import User

pytestmark = pytest.mark.django_db


def _running(user: User) -> tuple[BackgroundJob, JobAttempt]:
    job, _ = request_export(user)
    attempt = job.attempts.get()
    assert claim_attempt(str(job.id), str(attempt.id), str(attempt.task_id)) is not None
    job.refresh_from_db()
    attempt.refresh_from_db()
    return job, attempt


def _publish(attempt: JobAttempt, *, partial: bool = False) -> bool:
    return publish_artifact(
        attempt.id,
        filename="export.zip",
        size_bytes=123,
        sha256="a" * 64,
        summary={"omissions": []},
        partial_result=partial,
    )


def test_database_rejects_two_active_jobs(user: User) -> None:
    job, created = request_export(user)
    assert created
    same, created_again = request_export(user)
    assert same.pk == job.pk
    assert not created_again
    with pytest.raises(IntegrityError), transaction.atomic():
        BackgroundJob.objects.create(requester=user)


def test_inactive_account_cannot_request_an_export(user: User) -> None:
    user.is_active = False
    user.save(update_fields=["is_active"])
    with pytest.raises(ExportUnavailableError, match="account is inactive"):
        request_export(user)
    assert not BackgroundJob.objects.filter(requester=user).exists()


def test_celery_generation_limits_match_export_settings(settings: Settings) -> None:
    assert generate_export.soft_time_limit == settings.EXPORTS_SOFT_TIME_LIMIT
    assert generate_export.time_limit == settings.EXPORTS_HARD_TIME_LIMIT


@pytest.mark.parametrize("hard_limit", [13, 73])
def test_attempt_deadline_and_scratch_cleanup_follow_configured_hard_limit(
    user: User, settings: Settings, tmp_path: Path, hard_limit: int
) -> None:
    settings.EXPORTS_HARD_TIME_LIMIT = hard_limit
    _job, attempt = _running(user)
    assert attempt.deadline_at is not None
    assert attempt.started_at is not None
    assert attempt.deadline_at - attempt.started_at == timedelta(seconds=hard_limit)

    abandoned: Path = tmp_path / f"attempt-{uuid.uuid4()}_old"
    current: Path = tmp_path / f"attempt-{uuid.uuid4()}_current"
    active: Path = tmp_path / f"attempt-{attempt.pk}_active"
    old_timestamp: float = (
        timezone.now() - timedelta(seconds=hard_limit) - timedelta(minutes=6)
    ).timestamp()
    for directory in (abandoned, current, active):
        directory.mkdir()
        (directory / "archive.zip").write_bytes(b"export data")
    for directory in (abandoned, active):
        os.utime(directory, (old_timestamp, old_timestamp))

    _clean_scratch(tmp_path)

    assert not abandoned.exists()
    assert (current / "archive.zip").read_bytes() == b"export data"
    assert (active / "archive.zip").read_bytes() == b"export data"


def test_unexpected_task_id_cannot_claim_and_duplicates_cannot_overwrite_results(
    user: User,
) -> None:
    job, _ = request_export(user)
    attempt = job.attempts.get()
    assert claim_attempt(str(job.pk), str(attempt.pk), str(uuid.uuid4())) is None
    assert claim_attempt(str(job.pk), str(attempt.pk), str(attempt.task_id)) is not None
    TaskResult.objects.create(task_id=str(attempt.task_id), status="STARTED")
    with pytest.raises(Ignore):
        generate_export.run(str(job.pk), str(attempt.pk))
    assert TaskResult.objects.get(task_id=str(attempt.task_id)).status == "STARTED"


def test_retry_cycle_is_bounded_and_fresh_attempt_keeps_history(user: User) -> None:
    job, attempt = _running(user)
    keys: set[str] = set()
    for number in range(1, 4):
        attempt.refresh_from_db()
        assert attempt.object_key.startswith("exports/speleodb-export-")
        assert attempt.object_key.endswith(f"-{attempt.id}.zip")
        assert attempt.object_key.count("/") == 1
        assert attempt.object_key not in keys
        keys.add(attempt.object_key)
        fail_attempt(attempt.pk, "Source unavailable")
        job.refresh_from_db()
        attempt.refresh_from_db()
        assert attempt.finished_at is not None
        if number < 3:  # noqa: PLR2004
            assert job.state == JobState.RETRY_WAIT
            assert job.next_attempt_at is not None
            retry_due_jobs(job.next_attempt_at + timedelta(seconds=1))
            job.refresh_from_db()
            assert job.current_attempt_id is not None
            attempt = job.attempts.get(pk=job.current_attempt_id)
            assert attempt.cycle_attempt == number + 1
            assert (
                claim_attempt(str(job.pk), str(attempt.pk), str(attempt.task_id))
                is not None
            )
    assert job.state == JobState.FAILED
    assert job.attempts.count() == 3  # noqa: PLR2004
    retried = retry_export(job, user)
    assert retried.state == JobState.QUEUED
    assert retried.current_attempt_id is not None
    assert retried.attempts.get(pk=retried.current_attempt_id).cycle_attempt == 1
    assert retried.attempts.count() == 4  # noqa: PLR2004


def test_stale_attempt_cannot_publish_or_fail_a_new_attempt(user: User) -> None:
    job, old = _running(user)
    fail_attempt(old.id, "Interrupted")
    job.refresh_from_db()
    assert job.next_attempt_at is not None
    retry_due_jobs(job.next_attempt_at + timedelta(seconds=1))
    job.refresh_from_db()
    assert job.current_attempt_id is not None
    new = job.attempts.get(pk=job.current_attempt_id)
    claim_attempt(str(job.id), str(new.id), str(new.task_id))
    assert not _publish(old)
    fail_attempt(old.id, "Late failure")
    job.refresh_from_db()
    assert job.state == JobState.RUNNING
    assert job.current_attempt_id == new.id


def test_publication_is_once_and_expiry_starts_at_ready(user: User) -> None:
    job, attempt = _running(user)
    before = timezone.now()
    assert _publish(attempt, partial=True)
    assert not _publish(attempt)
    job.refresh_from_db()
    assert job.state == JobState.PARTIAL
    assert job.completed_items == job.total_items
    assert job.total_items >= 1
    artifact = JobArtifact.objects.get(job=job)
    assert artifact.ready_at >= before
    assert artifact.expires_at - artifact.ready_at == timedelta(hours=24)
    fail_attempt(attempt.id, "Late result-backend failure")
    job.refresh_from_db()
    assert job.state == JobState.PARTIAL
    with pytest.raises(ExportConflictError):
        retry_export(job, user)


def test_deadline_prevents_publication(user: User) -> None:
    _, attempt = _running(user)
    JobAttempt.objects.filter(pk=attempt.pk).update(
        deadline_at=timezone.now() - timedelta(seconds=1)
    )
    assert not _publish(attempt)
    assert not JobArtifact.objects.exists()


def test_expiry_enforced_without_cleanup_and_staff_cannot_download(user: User) -> None:
    job, attempt = _running(user)
    assert _publish(attempt)
    staff = UserFactory.create(is_staff=True)
    with pytest.raises(PermissionDenied):
        artifact_download_url(job, staff)
    JobArtifact.objects.filter(job=job).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    with pytest.raises(ExportExpiredError):
        artifact_download_url(job, user)
    with pytest.raises(ExportExpiredError):
        request_notification(job, user)
    assert JobArtifact.objects.get(job=job).deleted_at is None


def test_email_is_independent_and_duplicate_delivery_is_guarded(user: User) -> None:
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    job, attempt = _running(user)
    assert _publish(attempt)
    result = send_export_notification.run(str(job.id))
    assert result["notification"] == "sent"
    assert len(mail.outbox) == 1
    assert "/private/exports/" in mail.outbox[0].body
    assert "Sign in" in mail.outbox[0].body
    assert "123 bytes" in mail.outbox[0].body
    assert "Available until" in mail.outbox[0].body
    assert isinstance(mail.outbox[0], EmailMultiAlternatives)
    assert len(mail.outbox[0].alternatives) == 1
    html_body: str = str(mail.outbox[0].alternatives[0][0])
    assert "123 bytes" in html_body
    assert "Available until" in html_body
    assert 'href="' in html_body
    assert "X-Amz" not in mail.outbox[0].body
    assert send_export_notification.run(str(job.id))["notification"] == "ignored"
    assert len(mail.outbox) == 1
    job.refresh_from_db()
    assert job.state == JobState.READY
    assert job.attempts.count() == 1


def test_email_html_escapes_artifact_metadata(user: User) -> None:
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    job, attempt = _running(user)
    assert _publish(attempt)
    JobArtifact.objects.filter(job=job).update(
        filename='backup<script>alert("x")</script>.zip'
    )
    result = send_export_notification.run(str(job.id))
    assert result["notification"] == "sent"
    assert isinstance(mail.outbox[0], EmailMultiAlternatives)
    html_body: str = str(mail.outbox[0].alternatives[0][0])
    assert "<script>" not in html_body
    assert "&lt;script&gt;" in html_body


def test_unverified_email_retries_without_regenerating(user: User) -> None:
    job, attempt = _running(user)
    assert _publish(attempt)
    expires_at = JobArtifact.objects.get(job=job).expires_at
    assert send_export_notification.run(str(job.id))["notification"] == "pending"
    job.refresh_from_db()
    assert job.notification_attempts == 1
    assert job.state == JobState.READY
    assert job.attempts.count() == 1
    assert JobArtifact.objects.get(job=job).expires_at == expires_at


def test_notification_attempts_are_bounded_and_manual_resend_is_independent(
    user: User,
    settings: Settings,
) -> None:
    job, attempt = _running(user)
    assert _publish(attempt)
    artifact: JobArtifact = JobArtifact.objects.get(job=job)
    for number in range(1, settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS + 1):
        BackgroundJob.objects.filter(pk=job.pk).update(
            notification_due_at=timezone.now() - timedelta(seconds=1)
        )
        result: dict[str, str] = send_export_notification.run(str(job.pk))
        assert result["notification"] == (
            "failed"
            if number == settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS
            else "pending"
        )
    job.refresh_from_db()
    assert job.state == JobState.READY
    assert job.notification_due_at is None
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    request_notification(job, user)
    assert send_export_notification.run(str(job.pk))["notification"] == "sent"
    artifact.refresh_from_db()
    assert artifact.attempt_id == attempt.pk
    assert job.attempts.count() == 1


def test_smtp_failure_retries_email_without_rebuilding(
    user: User,
    settings: Settings,
) -> None:
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    job, attempt = _running(user)
    assert _publish(attempt)
    artifact: JobArtifact = JobArtifact.objects.get(job=job)
    expiry = artifact.expires_at
    original_backend: str = settings.EMAIL_BACKEND
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.EMAIL_HOST = "127.0.0.1"
        settings.EMAIL_PORT = unavailable.getsockname()[1]
        settings.EMAIL_TIMEOUT = 1
        settings.EMAIL_USE_TLS = False
        settings.EMAIL_USE_SSL = False
        settings.EMAIL_HOST_USER = ""
        settings.EMAIL_HOST_PASSWORD = ""
        assert send_export_notification.run(str(job.pk))["notification"] == "pending"
    job.refresh_from_db()
    assert job.state == JobState.READY
    assert "Email delivery failed" in job.notification_error
    assert len(mail.outbox) == 0
    settings.EMAIL_BACKEND = original_backend
    BackgroundJob.objects.filter(pk=job.pk).update(
        notification_due_at=timezone.now() - timedelta(seconds=1)
    )
    assert send_export_notification.run(str(job.pk))["notification"] == "sent"
    artifact.refresh_from_db()
    assert artifact.expires_at == expiry
    assert artifact.attempt_id == attempt.pk
    assert job.attempts.count() == 1
    assert len(mail.outbox) == 1


def test_maintenance_recovers_dead_workers_after_grace_period(user: User) -> None:
    job, attempt = _running(user)
    JobAttempt.objects.filter(pk=attempt.pk).update(
        deadline_at=timezone.now() - timedelta(minutes=4)
    )
    maintain_background_jobs.run()
    job.refresh_from_db()
    assert job.state == JobState.RUNNING
    JobAttempt.objects.filter(pk=attempt.pk).update(
        deadline_at=timezone.now() - timedelta(minutes=6)
    )
    maintain_background_jobs.run()
    job.refresh_from_db()
    attempt.refresh_from_db()
    assert job.state == JobState.RETRY_WAIT
    assert attempt.state == JobState.FAILED
    assert "worker stopped" in attempt.error
    assert job.attempts.count() == 1
    BackgroundJob.objects.filter(pk=job.pk).update(
        next_attempt_at=timezone.now() - timedelta(seconds=1)
    )
    maintain_background_jobs.run()
    job.refresh_from_db()
    assert job.state == JobState.QUEUED
    assert job.current_attempt_id != attempt.pk
    assert job.attempts.count() == 2  # noqa: PLR2004


def test_lost_notification_lease_is_recoverable(user: User) -> None:
    job, attempt = _running(user)
    assert _publish(attempt)
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    token: uuid.UUID = uuid.uuid4()
    BackgroundJob.objects.filter(pk=job.pk).update(
        notification_state="sending",
        notification_attempts=1,
        notification_token=token,
        notification_due_at=timezone.now() + timedelta(minutes=1),
    )
    maintain_background_jobs.run()
    job.refresh_from_db()
    assert job.notification_token == token
    with pytest.raises(ExportConflictError):
        request_notification(job, user)
    BackgroundJob.objects.filter(pk=job.pk).update(
        notification_due_at=timezone.now() - timedelta(seconds=1)
    )
    maintain_background_jobs.run()
    job.refresh_from_db()
    assert job.notification_state == "pending"
    assert job.notification_token is None
    assert job.notification_due_at is not None
    assert job.notification_due_at > timezone.now()
    assert send_export_notification.run(str(job.pk))["notification"] == "ignored"
    BackgroundJob.objects.filter(pk=job.pk).update(
        notification_due_at=timezone.now() - timedelta(seconds=1)
    )
    assert send_export_notification.run(str(job.pk))["notification"] == "sent"
    assert len(mail.outbox) == 1
    assert job.attempts.count() == 1


def test_lost_final_notification_lease_requires_manual_retry(
    user: User, settings: Settings
) -> None:
    job, attempt = _running(user)
    assert _publish(attempt)
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    artifact: JobArtifact = JobArtifact.objects.get(job=job)
    expiry = artifact.expires_at
    BackgroundJob.objects.filter(pk=job.pk).update(
        notification_state="sending",
        notification_attempts=settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS,
        notification_token=uuid.uuid4(),
        notification_due_at=timezone.now() - timedelta(seconds=1),
    )

    maintain_background_jobs.run()
    job.refresh_from_db()
    assert job.notification_state == "failed"
    assert job.notification_token is None
    assert job.notification_due_at is None
    assert "could not be confirmed" in job.notification_error
    assert send_export_notification.run(str(job.pk))["notification"] == "ignored"
    assert len(mail.outbox) == 0

    request_notification(job, user)
    assert send_export_notification.run(str(job.pk))["notification"] == "sent"
    job.refresh_from_db()
    artifact.refresh_from_db()
    assert job.notification_attempts == 1
    assert len(mail.outbox) == 1
    assert artifact.expires_at == expiry
    assert artifact.attempt_id == attempt.pk
    assert job.attempts.count() == 1


def test_scheduler_installation_is_idempotent_and_uses_control_queue() -> None:
    call_command("install_background_schedules")
    call_command("install_background_schedules")
    tasks = PeriodicTask.objects.filter(
        name__in=[
            "background-job-maintenance",
            "export-artifact-cleanup",
            "celery.backend_cleanup",
        ]
    )
    assert tasks.count() == 3  # noqa: PLR2004
    assert set(tasks.values_list("queue", flat=True)) == {"background_control"}
    assert not tasks.filter(interval__isnull=True).exists()
