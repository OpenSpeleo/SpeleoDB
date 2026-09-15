"""Archive work and short maintenance tasks on separate Celery queues."""

from __future__ import annotations

import logging
import shutil
import time
import uuid
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import Any

from allauth.account.models import EmailAddress
from celery import current_app
from celery import shared_task
from celery.exceptions import Ignore
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from speleodb.background_jobs.archive import build_archive
from speleodb.background_jobs.archive_sources import ArchiveBuildError
from speleodb.background_jobs.models import BackgroundJob
from speleodb.background_jobs.models import JobArtifact
from speleodb.background_jobs.models import JobAttempt
from speleodb.background_jobs.models import JobState
from speleodb.background_jobs.services import claim_attempt
from speleodb.background_jobs.services import dispatch_attempt
from speleodb.background_jobs.services import dispatch_notification
from speleodb.background_jobs.services import fail_attempt
from speleodb.background_jobs.services import fail_notification
from speleodb.background_jobs.services import publish_artifact
from speleodb.background_jobs.services import retry_delay
from speleodb.background_jobs.services import retry_due_jobs
from speleodb.background_jobs.storage import delete_archive
from speleodb.background_jobs.storage import upload_archive
from speleodb.users.models import User

if TYPE_CHECKING:
    from datetime import datetime

    from django.db.models import QuerySet

logger = logging.getLogger(__name__)
PROGRESS_INTERVAL_SECONDS: int = 5


class ExportExecutionError(RuntimeError):
    """A safe error suitable for Celery results and operator dashboards."""


def _emit_progress(
    *,
    task_id: str,
    task_name: str,
    job_id: str,
    stage: str,
    completed: int,
    total: int,
) -> None:
    """Publish optional dashboard observations without changing job ownership."""
    try:
        with (
            current_app.connection_for_write(connect_timeout=1) as connection,
            current_app.events.Dispatcher(
                connection=connection, buffer_while_offline=False
            ) as dispatcher,
        ):
            dispatcher.send(
                "kanchi-task-progress",
                task_id=task_id,
                task_name=task_name,
                progress=round(completed * 100 / total) if total else 0,
                message=stage,
                meta={"current": completed, "total": total},
                retry=False,
            )
    except Exception:  # noqa: BLE001 - Optional telemetry cannot fail an export.
        logger.debug("Export progress event unavailable", extra={"job_id": job_id})


def _clean_scratch(root: Path) -> None:
    """Reclaim abandoned directories on this worker, never another active attempt."""
    # Wait a full attempt budget plus the existing worker-recovery grace.
    cutoff = (
        timezone.now()
        - timedelta(seconds=settings.EXPORTS_HARD_TIME_LIMIT)
        - timedelta(minutes=5)
    )
    for directory in root.glob("attempt-*"):
        if directory.is_symlink() or not directory.is_dir():
            continue
        if directory.stat().st_mtime >= cutoff.timestamp():
            continue
        attempt_id = directory.name.removeprefix("attempt-").split("_", 1)[0]
        try:
            parsed_id = uuid.UUID(attempt_id)
        except ValueError:
            continue
        if not JobAttempt.objects.filter(
            pk=parsed_id, state=JobState.RUNNING, deadline_at__gt=cutoff
        ).exists():
            shutil.rmtree(directory)


@shared_task(
    bind=True,
    name="speleodb.background_jobs.tasks.generate_export",
    track_started=False,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=settings.EXPORTS_SOFT_TIME_LIMIT,
    time_limit=settings.EXPORTS_HARD_TIME_LIMIT,
)
def generate_export(self: Any, job_id: str, attempt_id: str) -> dict[str, Any]:
    attempt = claim_attempt(job_id, attempt_id, str(self.request.id))
    if attempt is None:
        raise Ignore
    last_update: float = 0.0
    last_stage: str = ""

    def progress(stage: str, completed: int, total: int) -> None:
        nonlocal last_update, last_stage
        now = time.monotonic()
        if (
            stage == last_stage
            and now - last_update < PROGRESS_INTERVAL_SECONDS
            and completed != total
        ):
            return
        updated = BackgroundJob.objects.filter(
            pk=job_id,
            current_attempt_id=attempt.id,
            state=JobState.RUNNING,
        ).update(
            stage=stage,
            completed_items=completed,
            total_items=total,
            updated_at=timezone.now(),
        )
        if not updated:
            raise ExportExecutionError("This export attempt has been superseded.")
        last_update, last_stage = now, stage
        _emit_progress(
            task_id=str(self.request.id),
            task_name=self.name,
            job_id=job_id,
            stage=stage,
            completed=completed,
            total=total,
        )

    failure: str | None = None
    try:
        # Celery's automatic STARTED write runs before this function's claim
        # guard, so only the successfully claimed invocation may record it.
        self.update_state(
            state="STARTED", meta={"job_id": job_id, "attempt_id": attempt_id}
        )
        owner = User.objects.get(pk=attempt.job.requester_id, is_active=True)
        root = Path(settings.EXPORTS_SCRATCH_DIR)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        _clean_scratch(root)
        with TemporaryDirectory(prefix=f"attempt-{attempt.id}_", dir=root) as temporary:
            path = Path(temporary) / "archive.zip"
            result = build_archive(user=owner, destination=path, progress=progress)
            progress("Uploading archive", 0, 1)
            filename: str = Path(attempt.object_key).name
            upload_archive(
                path, key=attempt.object_key, filename=filename, sha256=result.sha256
            )
            published = publish_artifact(
                attempt.id,
                filename=filename,
                size_bytes=result.size_bytes,
                sha256=result.sha256,
                summary={
                    "omissions": result.manifest.get("omissions", []),
                    "notes": result.manifest.get("notes", []),
                    "file_count": sum(
                        len(resource.get("files", []))
                        for resource in result.manifest.get("resources", [])
                    ),
                },
                partial_result=result.partial,
            )
            if not published:
                raise ExportExecutionError(  # noqa: TRY301 - Use the task failure boundary.
                    "This export attempt expired before publication."
                )
            _emit_progress(
                task_id=str(self.request.id),
                task_name=self.name,
                job_id=job_id,
                stage="Ready with omissions" if result.partial else "Ready",
                completed=1,
                total=1,
            )
        return {"job_id": job_id, "state": "partial" if result.partial else "ready"}
    except Exception as error:  # noqa: BLE001 - Record a safe terminal attempt outcome.
        # Credential-bearing dependency exceptions must not enter task results,
        # progress events, or notifications. Keep the error category for diagnosis.
        failure = (
            str(error)
            if isinstance(error, (ArchiveBuildError, ExportExecutionError))
            else f"Archive generation failed ({type(error).__name__})."
        )
        fail_attempt(attempt.id, failure)
        logger.error(  # noqa: TRY400 - Dependency tracebacks may contain credentials.
            "Export attempt failed",
            extra={
                "job_id": job_id,
                "attempt_id": attempt_id,
                "error_type": type(error).__name__,
            },
        )
    # Raise outside the handler to avoid serializing the dependency exception chain.
    raise ExportExecutionError(failure)


@shared_task(name="speleodb.background_jobs.tasks.maintain_background_jobs")
def maintain_background_jobs() -> None:
    now = timezone.now()
    for attempt_id in (
        JobAttempt.objects.filter(
            state=JobState.RUNNING,
            deadline_at__lt=now - timedelta(minutes=5),
        )
        .values_list("id", flat=True)
        .iterator()
    ):
        fail_attempt(
            attempt_id, "The worker stopped or exceeded its execution deadline."
        )
    retry_due_jobs(now)
    for attempt_id in (
        JobAttempt.objects.filter(
            state=JobState.QUEUED,
            dispatch_after__lte=now,
        )
        .values_list("id", flat=True)
        .iterator()
    ):
        dispatch_attempt(attempt_id)
    # A lost process has an ambiguous delivery outcome and still consumes an
    # attempt. Exhausted leases require an explicit operator retry.
    for job_id, token in (
        BackgroundJob.objects.filter(
            notification_state__in=["queued", "sending"],
            notification_due_at__lt=now,
        )
        .values_list("id", "notification_token")
        .iterator()
    ):
        fail_notification(
            job_id,
            token,
            "Notification publication or delivery could not be confirmed.",
        )
    for job_id in (
        BackgroundJob.objects.filter(
            state__in=[JobState.READY, JobState.PARTIAL, JobState.FAILED],
            notification_state="pending",
            notification_due_at__lte=now,
            notification_attempts__lt=settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS,
        )
        .values_list("id", flat=True)
        .iterator()
    ):
        dispatch_notification(job_id)


@shared_task(name="speleodb.background_jobs.tasks.send_export_notification")
def send_export_notification(
    job_id: str, dispatch_token: str | None = None
) -> dict[str, str]:
    now = timezone.now()
    token = uuid.UUID(dispatch_token) if dispatch_token is not None else uuid.uuid4()
    with transaction.atomic():
        job = (
            BackgroundJob.objects.select_for_update()
            .filter(
                pk=job_id,
                state__in=[JobState.READY, JobState.PARTIAL, JobState.FAILED],
            )
            .first()
        )
        if job is None:
            return {"job_id": job_id, "notification": "ignored"}
        if dispatch_token is None:
            if (
                job.notification_state != "pending"
                or job.notification_due_at is None
                or job.notification_due_at > now
                or job.notification_attempts
                >= settings.EXPORTS_MAX_NOTIFICATION_ATTEMPTS
            ):
                return {"job_id": job_id, "notification": "ignored"}
            job.notification_attempts += 1
        elif (
            job.notification_state != "queued"
            or job.notification_token != token
            or job.notification_due_at is None
            or job.notification_due_at <= now
        ):
            return {"job_id": job_id, "notification": "ignored"}
        job.notification_state = "sending"
        job.notification_token = token
        job.notification_due_at = now + timedelta(
            seconds=settings.EXPORTS_DISPATCH_LEASE_SECONDS
        )
        job.save(
            update_fields=[
                "notification_state",
                "notification_token",
                "notification_attempts",
                "notification_due_at",
                "updated_at",
            ]
        )
    error: str = ""
    try:
        recipient = (
            EmailAddress.objects.filter(
                user_id=job.requester_id,
                verified=True,
                primary=True,
                user__is_active=True,
            )
            .values_list("email", flat=True)
            .first()
        )
        if recipient is None:
            raise ExportExecutionError(  # noqa: TRY301 - Persist notification failures.
                "A verified primary email address is required."
            )
        artifact = JobArtifact.objects.filter(job=job).first()
        if artifact is not None and artifact.expires_at <= timezone.now():
            raise ExportExecutionError(  # noqa: TRY301 - Persist notification failures.
                "The export expired before the notification could be sent."
            )
        base = settings.EXPORTS_PUBLIC_BASE_URL
        if not base:
            base = f"https://{Site.objects.get_current().domain}"
        url = f"{base.rstrip('/')}{reverse('private:user_exports')}?export={job.id}"
        if job.state == JobState.FAILED:
            subject = "Your SpeleoDB export failed"
            body = (
                "We could not generate your archive. "
                "You can review the request and retry from your account."
            )
        elif job.state == JobState.PARTIAL:
            subject = "Your SpeleoDB export is ready with omissions"
            body = (
                "Your archive is ready. Some items could not be included; "
                "review the omissions before using this backup."
            )
        else:
            subject = "Your SpeleoDB export is ready"
            body = "Your archive is ready to download."
        context: dict[str, Any] = {
            "subject": subject,
            "message": body,
            "url": url,
            "has_artifact": artifact is not None,
            "filename": artifact.filename if artifact is not None else "",
            "size_bytes": artifact.size_bytes if artifact is not None else 0,
            "expires_at": artifact.expires_at if artifact is not None else None,
        }
        text_body: str = render_to_string(
            "background_jobs/export_notification.txt", context
        )
        html_body: str = render_to_string(
            "background_jobs/export_notification.html", context
        )
        if (
            send_mail(
                subject,
                text_body,
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=False,
                html_message=html_body,
            )
            != 1
        ):
            raise ExportExecutionError(  # noqa: TRY301 - Persist notification failures.
                "The email provider did not accept the message."
            )
    except Exception as failure:  # noqa: BLE001 - Email failures must not rebuild archives.
        error = (
            str(failure)
            if isinstance(failure, ExportExecutionError)
            else f"Email delivery failed ({type(failure).__name__})."
        )
    if error:
        fail_notification(job.pk, token, error)
        job.refresh_from_db()
        state = job.notification_state
    else:
        updated = BackgroundJob.objects.filter(
            pk=job_id, notification_token=token, notification_state="sending"
        ).update(
            notification_state="sent",
            notification_error="",
            notification_token=None,
            notification_due_at=None,
            updated_at=timezone.now(),
        )
        state = "sent" if updated else "ignored"
    return {"job_id": job_id, "notification": state}


def _cleanup_candidates(now: datetime) -> QuerySet[JobAttempt]:
    return (
        JobAttempt.objects.filter(
            object_deleted_at__isnull=True,
            cleanup_attempts__lt=settings.EXPORTS_MAX_CLEANUP_ATTEMPTS,
        )
        .exclude(object_key="")
        .filter(Q(cleanup_due_at__isnull=True) | Q(cleanup_due_at__lte=now))
        .filter(
            Q(artifact__expires_at__lte=now, artifact__deleted_at__isnull=True)
            | Q(
                state=JobState.FAILED,
                deadline_at__lt=now - timedelta(minutes=5),
                artifact__isnull=True,
            )
        )
    )


def _delete_attempt_object(attempt_id: uuid.UUID, now: datetime) -> None:
    token = uuid.uuid4()
    with transaction.atomic():
        attempt = (
            _cleanup_candidates(now)
            .select_for_update(of=("self",))
            .filter(pk=attempt_id)
            .first()
        )
        if attempt is None:
            return
        attempt.cleanup_attempts += 1
        attempt.cleanup_token = token
        attempt.cleanup_due_at = (
            now
            + timedelta(seconds=settings.EXPORTS_CLEANUP_LEASE_SECONDS)
            + retry_delay(attempt.cleanup_attempts)
        )
        # An interrupted final call must leave an actionable error as well.
        attempt.cleanup_error = "Object deletion has not been confirmed."
        attempt.save(
            update_fields=[
                "cleanup_attempts",
                "cleanup_token",
                "cleanup_due_at",
                "cleanup_error",
            ]
        )
    error: str = ""
    try:
        delete_archive(key=attempt.object_key)
    except Exception as failure:  # noqa: BLE001 - Persist a finite per-object retry budget.
        error = f"Deletion failed ({type(failure).__name__})."
    with transaction.atomic():
        current = (
            JobAttempt.objects.select_for_update()
            .filter(pk=attempt_id, cleanup_token=token)
            .first()
        )
        if current is None:
            return
        current.cleanup_token = None
        current.cleanup_error = error
        current.cleanup_due_at = (
            timezone.now() + retry_delay(current.cleanup_attempts)
            if error
            and current.cleanup_attempts < settings.EXPORTS_MAX_CLEANUP_ATTEMPTS
            else None
        )
        if not error:
            current.object_deleted_at = timezone.now()
        current.save(
            update_fields=[
                "cleanup_token",
                "cleanup_error",
                "cleanup_due_at",
                "object_deleted_at",
            ]
        )
        JobArtifact.objects.filter(attempt_id=attempt_id).update(
            delete_error=error, deleted_at=current.object_deleted_at
        )


@shared_task(name="speleodb.background_jobs.tasks.delete_expired_artifacts")
def delete_expired_artifacts() -> None:
    now = timezone.now()
    for attempt_id in _cleanup_candidates(now).values_list("id", flat=True).iterator():
        _delete_attempt_object(attempt_id, now)
    # Keep records until every tracked object has been removed successfully.
    retained = (
        JobAttempt.objects.filter(object_deleted_at__isnull=True)
        .exclude(object_key="")
        .values("job_id")
    )
    expired_history = (
        BackgroundJob.objects.filter(
            state__in=[JobState.READY, JobState.PARTIAL, JobState.FAILED],
            updated_at__lt=now - timedelta(days=90),
        )
        .exclude(pk__in=retained)
        .filter(Q(artifact__isnull=True) | Q(artifact__deleted_at__isnull=False))
    )
    for job_id in expired_history.values_list("id", flat=True).iterator():
        # Django collects cascading children before deleting the parent. Lock
        # and recheck each job so a concurrent retry cannot be collected and
        # deleted after its request has already been accepted.
        with transaction.atomic():
            job = (
                expired_history.select_for_update(of=("self",))
                .filter(pk=job_id)
                .first()
            )
            if job is not None:
                job.delete()
