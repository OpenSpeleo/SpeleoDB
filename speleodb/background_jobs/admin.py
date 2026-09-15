"""Read-only job diagnostics and application-authorized recovery actions."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlencode
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.db.models import Count
from django.db.models import Max
from django.db.models import Min
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.timesince import timesince
from django_celery_results.admin import GroupResultAdmin as CeleryGroupResultAdmin
from django_celery_results.admin import TaskResultAdmin as CeleryTaskResultAdmin
from django_celery_results.models import GroupResult
from django_celery_results.models import TaskResult

from speleodb.background_jobs.models import BackgroundJob
from speleodb.background_jobs.models import JobArtifact
from speleodb.background_jobs.models import JobAttempt
from speleodb.background_jobs.models import JobState
from speleodb.background_jobs.services import ExportConflictError
from speleodb.background_jobs.services import ExportExpiredError
from speleodb.background_jobs.services import ExportUnavailableError
from speleodb.background_jobs.services import request_export
from speleodb.background_jobs.services import request_notification
from speleodb.background_jobs.services import retry_cleanup as retry_job_cleanup
from speleodb.background_jobs.services import retry_export
from speleodb.users.models import User

if TYPE_CHECKING:
    from datetime import datetime

    from django.db.models import QuerySet
    from django.http import HttpRequest


class JobAttemptInline(admin.TabularInline):  # type: ignore[type-arg]
    model = JobAttempt
    extra = 0
    can_delete = False
    fields = (
        "number",
        "task_id",
        "task_result",
        "state",
        "created_at",
        "started_at",
        "finished_at",
        "error",
        "cleanup_attempts",
        "cleanup_due_at",
        "cleanup_error",
    )
    readonly_fields = fields

    @admin.display(description="Technical execution")
    def task_result(self, obj: JobAttempt) -> str:
        url: str = reverse("admin:django_celery_results_taskresult_changelist")
        query: str = urlencode({"task_id__exact": str(obj.task_id)})
        return format_html('<a href="{}?{}">View task results</a>', url, query)

    def has_add_permission(
        self, request: HttpRequest, obj: BackgroundJob | None = None
    ) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: BackgroundJob | None = None
    ) -> bool:
        return False

    def has_view_permission(
        self, request: HttpRequest, obj: BackgroundJob | None = None
    ) -> bool:
        return bool(request.user.is_active and request.user.is_staff)


@admin.register(BackgroundJob)
class BackgroundJobAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "id",
        "requester",
        "kind",
        "state",
        "stage",
        "age",
        "duration",
        "attempt_count",
        "attachment",
        "notification_state",
        "created_at",
    )
    list_filter = ("kind", "state", "notification_state", "created_at")
    search_fields = ("=id", "requester__email", "requester__name")
    ordering = ("-created_at",)
    list_per_page = 50
    inlines = [JobAttemptInline]
    actions = (
        "retry_failed",
        "retry_notifications",
        "retry_cleanup",
        "replace_partial",
    )
    readonly_fields = (
        "id",
        "requester",
        "kind",
        "state",
        "stage",
        "completed_items",
        "total_items",
        "created_at",
        "updated_at",
        "next_attempt_at",
        "summary",
        "notification_state",
        "notification_error",
        "notification_attempts",
        "notification_due_at",
        "attachment",
        "artifact_metadata",
        "kanchi_dashboard",
        "download_link",
    )

    def has_module_permission(self, request: HttpRequest) -> bool:
        return bool(request.user.is_active and request.user.is_staff)

    def has_view_permission(
        self, request: HttpRequest, obj: BackgroundJob | None = None
    ) -> bool:
        return self.has_module_permission(request)

    def has_change_permission(
        self, request: HttpRequest, obj: BackgroundJob | None = None
    ) -> bool:
        # Enable audited changelist actions, but forbid change-form submissions.
        return obj is None and self.has_module_permission(request)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: BackgroundJob | None = None
    ) -> bool:
        return False

    def get_fields(
        self, request: HttpRequest, obj: BackgroundJob | None = None
    ) -> tuple[str, ...]:
        return tuple(
            field
            for field in self.readonly_fields
            if field != "download_link" or request.user.is_superuser
        )

    def get_queryset(self, request: HttpRequest) -> QuerySet[BackgroundJob]:
        queryset: QuerySet[BackgroundJob] = super().get_queryset(request)
        return queryset.select_related("requester", "artifact__attempt").annotate(
            _attempt_count=Count("attempts"),
            _started_at=Min("attempts__started_at"),
            _finished_at=Max("attempts__finished_at"),
        )

    @admin.display(description="Age")
    def age(self, obj: BackgroundJob) -> str:
        return timesince(obj.created_at)

    @admin.display(description="Execution duration")
    def duration(self, obj: BackgroundJob) -> str:
        started: datetime | None = getattr(obj, "_started_at", None)
        finished: datetime | None = getattr(obj, "_finished_at", None)
        if started is None:
            return "—"
        if obj.state in {JobState.READY, JobState.PARTIAL, JobState.FAILED}:
            return timesince(started, finished) if finished else "—"
        return timesince(started)

    @admin.display(description="Attempts")
    def attempt_count(self, obj: BackgroundJob) -> int:
        return int(getattr(obj, "_attempt_count", 0))

    @admin.display(description="Attachment")
    def attachment(self, obj: BackgroundJob) -> str:
        artifact: JobArtifact | None = getattr(obj, "artifact", None)
        if artifact is None:
            return "Not ready"
        if artifact.deleted_at is not None:
            return "Deleted"
        if artifact.expires_at <= timezone.now():
            if (
                artifact.attempt.cleanup_attempts
                >= settings.EXPORTS_MAX_CLEANUP_ATTEMPTS
                and (
                    artifact.attempt.cleanup_due_at is None
                    or artifact.attempt.cleanup_due_at <= timezone.now()
                )
            ):
                return "Expired; cleanup retry required"
            return "Expired; deletion pending"
        return "Available"

    @admin.display(description="Artifact metadata")
    def artifact_metadata(self, obj: BackgroundJob) -> str:
        artifact: JobArtifact | None = getattr(obj, "artifact", None)
        if artifact is None:
            return "—"
        return (
            f"{artifact.filename} · {artifact.size_bytes:,} bytes · "
            f"SHA256 {artifact.sha256} · Expires {artifact.expires_at.isoformat()}"
        )

    @admin.display(description="Download (superusers)")
    def download_link(self, obj: BackgroundJob) -> str:
        if self.attachment(obj) != "Available":
            return "Unavailable"
        return format_html(
            '<a href="{}">Download ZIP</a>',
            reverse("api:v2:user-export-download", kwargs={"id": obj.pk}),
        )

    @admin.display(description="Operational dashboard")
    def kanchi_dashboard(self, obj: BackgroundJob) -> str:
        url: str = getattr(settings, "KANCHI_URL", "")
        if not url or urlsplit(url).scheme not in {"http", "https"}:
            return "Kanchi is not configured."
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">Open Kanchi</a>',
            url,
        )

    @staticmethod
    def _operator(request: HttpRequest) -> User:
        if not isinstance(request.user, User):
            msg: str = "An authenticated SpeleoDB user is required."
            raise TypeError(msg)
        return request.user

    @admin.action(description="Retry selected failed exports")
    def retry_failed(
        self, request: HttpRequest, queryset: QuerySet[BackgroundJob]
    ) -> None:
        count: int = 0
        for job in queryset.filter(kind="export", state=JobState.FAILED):
            try:
                retry_export(job, self._operator(request))
            except (ExportConflictError, ExportUnavailableError) as error:
                self.message_user(request, f"{job.pk}: {error}", messages.WARNING)
            else:
                self.log_change(request, job, "Requested a new export attempt.")
                count += 1
        self.message_user(request, f"Queued {count} failed export(s) for retry.")

    @admin.action(description="Retry failed notification emails")
    def retry_notifications(
        self, request: HttpRequest, queryset: QuerySet[BackgroundJob]
    ) -> None:
        count: int = 0
        for job in queryset.filter(kind="export", notification_state="failed"):
            try:
                request_notification(job, self._operator(request))
            except (
                ExportConflictError,
                ExportExpiredError,
                ExportUnavailableError,
            ) as error:
                self.message_user(request, f"{job.pk}: {error}", messages.WARNING)
            else:
                self.log_change(request, job, "Requested notification delivery retry.")
                count += 1
        self.message_user(request, f"Queued {count} notification(s) for retry.")

    @admin.action(description="Generate replacements for partial exports")
    def replace_partial(
        self, request: HttpRequest, queryset: QuerySet[BackgroundJob]
    ) -> None:
        count: int = 0
        for job in queryset.filter(
            kind="export", state=JobState.PARTIAL
        ).select_related("requester"):
            try:
                replacement, created = request_export(job.requester)
            except (ExportConflictError, ExportUnavailableError) as error:
                self.message_user(request, f"{job.pk}: {error}", messages.WARNING)
            else:
                self.log_change(
                    request, job, f"Replacement export requested: {replacement.pk}."
                )
                count += int(created)
        self.message_user(request, f"Created {count} replacement export(s).")

    @admin.action(description="Retry exhausted artifact cleanup")
    def retry_cleanup(
        self, request: HttpRequest, queryset: QuerySet[BackgroundJob]
    ) -> None:
        count = 0
        for job in queryset.filter(kind="export"):
            try:
                restarted = retry_job_cleanup(job, self._operator(request))
            except ExportUnavailableError as error:
                self.message_user(request, f"{job.pk}: {error}", messages.WARNING)
            else:
                if restarted:
                    self.log_change(
                        request,
                        job,
                        f"Reset cleanup retry budget for {restarted} object(s).",
                    )
                    count += restarted
        self.message_user(request, f"Queued {count} object(s) for cleanup retry.")


class ReadOnlyTechnicalResultAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Celery alone writes technical execution records, including for superusers."""

    actions = None

    def has_module_permission(self, request: HttpRequest) -> bool:
        return bool(request.user.is_active and request.user.is_staff)

    def has_view_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return self.has_module_permission(request)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return False


admin.site.unregister([TaskResult, GroupResult])


@admin.register(TaskResult)
class TaskResultAdmin(ReadOnlyTechnicalResultAdmin, CeleryTaskResultAdmin):
    """Keep upstream task diagnostics and filters with application permissions."""


@admin.register(GroupResult)
class GroupResultAdmin(ReadOnlyTechnicalResultAdmin, CeleryGroupResultAdmin):
    """Inspect Celery group results without granting mutation permissions."""
