"""Application-owned job lifecycle; Celery owns technical execution results."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from django.utils import timezone


class JobState(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    RETRY_WAIT = "retry_wait", "Waiting to retry"
    READY = "ready", "Ready"
    PARTIAL = "partial", "Ready with omissions"
    FAILED = "failed", "Failed"


ACTIVE_STATES: tuple[str, ...] = (
    JobState.QUEUED,
    JobState.RUNNING,
    JobState.RETRY_WAIT,
)


class BackgroundJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    requester_id: int
    kind = models.CharField(max_length=40, default="export", editable=False)
    state = models.CharField(max_length=20, choices=JobState, default=JobState.QUEUED)
    stage = models.CharField(max_length=100, default="Queued")
    completed_items = models.PositiveIntegerField(default=0)
    total_items = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict)
    current_attempt_id = models.UUIDField(null=True, editable=False)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    notification_state = models.CharField(max_length=20, default="pending")
    notification_error = models.TextField(blank=True)
    notification_attempts = models.PositiveSmallIntegerField(default=0)
    notification_due_at = models.DateTimeField(null=True, blank=True)
    notification_token = models.UUIDField(null=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    if TYPE_CHECKING:
        attempts: models.Manager[JobAttempt]
        artifact: JobArtifact

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["requester", "kind"],
                condition=models.Q(state__in=ACTIVE_STATES),
                name="background_one_active_per_user_kind",
            ),
        ]
        indexes = [
            models.Index(
                fields=["state", "next_attempt_at"], name="bg_job_state_next_idx"
            ),
            models.Index(
                fields=["requester", "-created_at"], name="bg_job_requester_date_idx"
            ),
            models.Index(
                fields=["notification_state", "notification_due_at"],
                name="bg_job_notify_due_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind}: {self.id} ({self.state})"


class JobAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        BackgroundJob, related_name="attempts", on_delete=models.CASCADE
    )
    job_id: uuid.UUID
    number = models.PositiveIntegerField()
    cycle_attempt = models.PositiveSmallIntegerField(default=1)
    task_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    state = models.CharField(max_length=20, choices=JobState, default=JobState.QUEUED)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    dispatch_after = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    deadline_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    object_key = models.CharField(max_length=500, blank=True)
    object_version = models.CharField(max_length=1024, blank=True)
    object_deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "number"], name="background_unique_attempt"
            ),
        ]
        indexes = [
            models.Index(
                fields=["state", "dispatch_after"], name="bg_attempt_dispatch_idx"
            ),
            models.Index(
                fields=["state", "deadline_at"], name="bg_attempt_deadline_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.job_id}: attempt {self.number}"


class JobArtifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.OneToOneField(
        BackgroundJob, related_name="artifact", on_delete=models.CASCADE
    )
    job_id: uuid.UUID
    attempt = models.OneToOneField(
        JobAttempt, related_name="artifact", on_delete=models.CASCADE
    )
    object_key = models.CharField(max_length=500, unique=True)
    object_version = models.CharField(max_length=1024, blank=True)
    filename = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    ready_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    delete_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-ready_at"]

    def __str__(self) -> str:
        return self.filename
