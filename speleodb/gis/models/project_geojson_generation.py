"""Durable, per-source work independent of request and broker availability."""

from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone

from speleodb.surveys.models import ProjectCommit


class GeoJSONGenerationState(models.TextChoices):
    PENDING = "pending", "Pending"
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    READY = "ready", "Ready"
    SKIPPED = "skipped", "Skipped"
    FAILED = "failed", "Failed"


class ProjectGeoJSONGeneration(models.Model):
    commit = models.OneToOneField(
        ProjectCommit,
        primary_key=True,
        related_name="geojson_generation",
        on_delete=models.CASCADE,
    )
    state = models.CharField(
        max_length=12,
        choices=GeoJSONGenerationState,
        default=GeoJSONGenerationState.PENDING,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    dispatch_attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, null=True, blank=True)
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=40, blank=True)
    last_error = models.CharField(max_length=2000, blank=True)
    unpublished_objects = models.JSONField(default=list, blank=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Project GeoJSON generation"
        indexes = [
            models.Index(
                fields=["state", "next_attempt_at"], name="gis_geojson_due_idx"
            ),
            models.Index(
                fields=["state", "lease_expires_at"], name="gis_geojson_lease_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.commit_id[:8]}: {self.state}"
