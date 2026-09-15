# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

from django.urls import reverse
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from speleodb.background_jobs.models import BackgroundJob
from speleodb.background_jobs.models import JobArtifact


class ExportArtifactSerializer(serializers.ModelSerializer[JobArtifact]):
    class Meta:
        model = JobArtifact
        fields = ["filename", "size_bytes", "sha256", "ready_at", "expires_at"]
        read_only_fields = fields


class UserExportSerializer(serializers.ModelSerializer[BackgroundJob]):
    artifact = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    expired = serializers.SerializerMethodField()

    class Meta:
        model = BackgroundJob
        fields = [
            "id",
            "state",
            "stage",
            "completed_items",
            "total_items",
            "summary",
            "created_at",
            "updated_at",
            "notification_state",
            "artifact",
            "download_url",
            "expired",
        ]
        read_only_fields = fields

    @extend_schema_field(ExportArtifactSerializer(allow_null=True))
    def get_artifact(self, obj: BackgroundJob) -> dict[str, Any] | None:
        artifact: JobArtifact | None = getattr(obj, "artifact", None)
        if artifact is None:
            return None
        return dict(ExportArtifactSerializer(artifact).data)

    def get_expired(self, obj: BackgroundJob) -> bool:
        artifact: JobArtifact | None = getattr(obj, "artifact", None)
        return artifact is not None and (
            artifact.deleted_at is not None or artifact.expires_at <= timezone.now()
        )

    def get_download_url(self, obj: BackgroundJob) -> str | None:
        artifact: JobArtifact | None = getattr(obj, "artifact", None)
        if (
            obj.state not in {"ready", "partial"}
            or artifact is None
            or self.get_expired(obj)
        ):
            return None
        return reverse("api:v2:user-export-download", kwargs={"id": obj.pk})
