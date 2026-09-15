"""Durable requests and fenced state transitions, independent of the broker UI."""

from __future__ import annotations

import logging
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING
from typing import Any

from celery import current_app
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from speleodb.background_jobs.models import ACTIVE_STATES
from speleodb.background_jobs.models import BackgroundJob
from speleodb.background_jobs.models import JobArtifact
from speleodb.background_jobs.models import JobAttempt
from speleodb.background_jobs.models import JobState
from speleodb.background_jobs.storage import signed_archive_url
from speleodb.users.models import User

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

logger = logging.getLogger(__name__)
GENERATION_TASK: str = "speleodb.background_jobs.tasks.generate_export"
NOTIFICATION_TASK: str = "speleodb.background_jobs.tasks.send_export_notification"


class ExportConflictError(ValueError):
    """An active request conflicts with this transition."""


class ExportUnavailableError(ValueError):
    """Creation or an artifact is currently unavailable."""


class ExportExpiredError(ValueError):
    """An archive's availability window has ended."""


def _new_attempt(job: BackgroundJob, *, cycle_attempt: int = 1) -> JobAttempt:
    number = (job.attempts.aggregate(last=Max("number"))["last"] or 0) + 1
    attempt = JobAttempt.objects.create(
        job=job, number=number, cycle_attempt=cycle_attempt
    )
    job.current_attempt_id = attempt.id
    job.state = JobState.QUEUED
    job.stage = "Queued"
    job.completed_items = 0
    job.total_items = 0
    job.summary = {}
    job.next_attempt_at = None
    job.notification_state = "pending"
    job.notification_due_at = None
    job.notification_token = None
    job.notification_attempts = 0
    job.notification_error = ""
    job.save()
    transaction.on_commit(partial(dispatch_attempt, attempt.id), robust=True)
    return attempt


def request_export(user: User) -> tuple[BackgroundJob, bool]:
    if not user.is_active:
        raise ExportUnavailableError("This account is inactive.")
    with transaction.atomic():
        # Serialize request/retry by requester, including the no-existing-row case.
        User.objects.select_for_update().get(pk=user.pk)
        existing = BackgroundJob.objects.filter(
            requester=user, kind="export", state__in=ACTIVE_STATES
        ).first()
        if existing is not None:
            return existing, False
        job = BackgroundJob.objects.create(requester=user)
        _new_attempt(job)
    return job, True


def _lock_existing_job(job_id: uuid.UUID) -> BackgroundJob:
    job = BackgroundJob.objects.select_for_update().filter(pk=job_id).first()
    if job is None:
        raise ExportUnavailableError(
            "This export is no longer available. Request a new export."
        )
    return job


def retry_export(job: BackgroundJob, user: User) -> BackgroundJob:
    if not user.is_active or not (user.is_staff or job.requester_id == user.pk):
        raise PermissionDenied
    with transaction.atomic():
        owner = User.objects.select_for_update().get(pk=job.requester_id)
        if not owner.is_active:
            raise ExportUnavailableError("This account is inactive.")
        job = _lock_existing_job(job.pk)
        if job.state != JobState.FAILED:
            raise ExportConflictError("Only failed exports can be retried.")
        if BackgroundJob.objects.filter(
            requester=owner, kind=job.kind, state__in=ACTIVE_STATES
        ).exists():
            raise ExportConflictError("This user already has an active export.")
        _new_attempt(job)
    return job


def dispatch_attempt(attempt_id: uuid.UUID) -> None:
    now = timezone.now()
    with transaction.atomic():
        attempt = (
            JobAttempt.objects.select_for_update()
            .filter(
                pk=attempt_id,
                state=JobState.QUEUED,
                dispatch_after__lte=now,
            )
            .first()
        )
        if attempt is None:
            return
        attempt.dispatch_after = now + timedelta(minutes=10)
        attempt.save(update_fields=["dispatch_after"])
        job_id, task_id = attempt.job_id, attempt.task_id
    try:
        current_app.send_task(
            GENERATION_TASK,
            args=[str(job_id), str(attempt_id)],
            task_id=str(task_id),
            queue="exports",
            retry=False,
        )
    except Exception:  # noqa: BLE001 - Accepted requests must survive broker failures.
        JobAttempt.objects.filter(pk=attempt_id, state=JobState.QUEUED).update(
            dispatch_after=now + timedelta(minutes=1),
        )
        logger.warning("Export dispatch deferred", extra={"job_id": str(job_id)})
    else:
        JobAttempt.objects.filter(pk=attempt_id).update(dispatched_at=now)


def claim_attempt(job_id: str, attempt_id: str, task_id: str) -> JobAttempt | None:
    with transaction.atomic():
        job = BackgroundJob.objects.select_for_update().filter(pk=job_id).first()
        if (
            job is None
            or str(job.current_attempt_id) != attempt_id
            or job.state != JobState.QUEUED
        ):
            return None
        attempt = (
            JobAttempt.objects.select_for_update()
            .filter(
                pk=attempt_id,
                job=job,
                task_id=task_id,
                state=JobState.QUEUED,
            )
            .first()
        )
        if attempt is None:
            return None
        now = timezone.now()
        attempt.state = JobState.RUNNING
        attempt.started_at = now
        attempt.deadline_at = now + timedelta(seconds=settings.EXPORTS_HARD_TIME_LIMIT)
        attempt.object_key = (
            f"exports/speleodb-export-{now:%Y-%m-%dT%H-%M-%SZ}-{attempt.id}.zip"
        )
        attempt.save()
        job.state = JobState.RUNNING
        job.stage = "Collecting accessible data"
        job.save(update_fields=["state", "stage", "updated_at"])
        return attempt


def fail_attempt(attempt_id: uuid.UUID, error: str) -> None:
    with transaction.atomic():
        reference = JobAttempt.objects.get(pk=attempt_id)
        job = BackgroundJob.objects.select_for_update().get(pk=reference.job_id)
        attempt = JobAttempt.objects.select_for_update().get(pk=attempt_id)
        if job.current_attempt_id != attempt.id or job.state != JobState.RUNNING:
            return
        now = timezone.now()
        attempt.state = JobState.FAILED
        attempt.error = error[:2000]
        attempt.finished_at = now
        attempt.save(update_fields=["state", "error", "finished_at"])
        job.summary = {"error": attempt.error}
        if attempt.cycle_attempt < settings.EXPORTS_MAX_ATTEMPTS:
            delay = 60 if attempt.cycle_attempt == 1 else 300
            job.state = JobState.RETRY_WAIT
            job.stage = "Waiting to retry"
            job.next_attempt_at = now + timedelta(seconds=delay)
        else:
            job.state = JobState.FAILED
            job.stage = "Export failed"
            job.notification_due_at = now
        job.save()


def publish_artifact(
    attempt_id: uuid.UUID,
    *,
    filename: str,
    size_bytes: int,
    sha256: str,
    version: str,
    summary: dict[str, Any],
    partial_result: bool,
) -> bool:
    with transaction.atomic():
        reference = JobAttempt.objects.get(pk=attempt_id)
        job = BackgroundJob.objects.select_for_update().get(pk=reference.job_id)
        attempt = JobAttempt.objects.select_for_update().get(pk=attempt_id)
        now = timezone.now()
        if (
            job.current_attempt_id != attempt.id
            or job.state != JobState.RUNNING
            or attempt.deadline_at is None
            or now >= attempt.deadline_at
        ):
            return False
        state = JobState.PARTIAL if partial_result else JobState.READY
        JobArtifact.objects.create(
            job=job,
            attempt=attempt,
            object_key=attempt.object_key,
            object_version=version,
            filename=filename,
            size_bytes=size_bytes,
            sha256=sha256,
            ready_at=now,
            expires_at=now + timedelta(hours=24),
        )
        attempt.state = state
        attempt.finished_at = now
        attempt.object_version = version
        attempt.save(update_fields=["state", "finished_at", "object_version"])
        job.state = state
        job.stage = "Ready with omissions" if partial_result else "Ready"
        job.total_items = max(job.total_items, 1)
        job.completed_items = job.total_items
        job.summary = summary
        job.notification_due_at = now
        job.save()
        return True


def artifact_download_url(job: BackgroundJob, user: User) -> str:
    if not user.is_active or not (user.is_superuser or job.requester_id == user.pk):
        raise PermissionDenied
    artifact = JobArtifact.objects.filter(job=job).first()
    if artifact is None:
        raise ExportUnavailableError("This archive is not ready.")
    remaining = int((artifact.expires_at - timezone.now()).total_seconds())
    if artifact.deleted_at is not None or remaining <= 0:
        raise ExportExpiredError("This archive has expired. Request a new export.")
    return signed_archive_url(
        key=artifact.object_key,
        version=artifact.object_version,
        expires=min(300, remaining),
        filename=artifact.filename,
    )


def request_notification(job: BackgroundJob, user: User) -> None:
    if not user.is_active or not (user.is_staff or user.pk == job.requester_id):
        raise PermissionDenied
    with transaction.atomic():
        job = _lock_existing_job(job.pk)
        if job.state not in (JobState.READY, JobState.PARTIAL, JobState.FAILED):
            raise ExportUnavailableError("This job has not completed.")
        if JobArtifact.objects.filter(job=job, expires_at__lte=timezone.now()).exists():
            raise ExportExpiredError("This archive has expired. Request a new export.")
        if job.notification_state == "sending":
            raise ExportConflictError("A notification is already being sent.")
        job.notification_state = "pending"
        job.notification_attempts = 0
        job.notification_due_at = timezone.now()
        job.notification_error = ""
        job.save(
            update_fields=[
                "notification_state",
                "notification_attempts",
                "notification_due_at",
                "notification_error",
                "updated_at",
            ]
        )


def retry_due_jobs(now: datetime) -> None:
    for job_id in (
        BackgroundJob.objects.filter(
            state=JobState.RETRY_WAIT, next_attempt_at__lte=now
        )
        .values_list("id", flat=True)
        .iterator()
    ):
        with transaction.atomic():
            reference = BackgroundJob.objects.get(pk=job_id)
            User.objects.select_for_update().get(pk=reference.requester_id)
            job = BackgroundJob.objects.select_for_update().get(pk=job_id)
            if job.state != JobState.RETRY_WAIT or job.current_attempt_id is None:
                continue
            previous = JobAttempt.objects.get(pk=job.current_attempt_id)
            _new_attempt(job, cycle_attempt=previous.cycle_attempt + 1)
