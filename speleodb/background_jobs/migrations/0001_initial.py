"""Persist application jobs, execution attempts, and expiring artifacts."""

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="BackgroundJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(default="export", editable=False, max_length=40)),
                ("state", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("retry_wait", "Waiting to retry"), ("ready", "Ready"), ("partial", "Ready with omissions"), ("failed", "Failed")], default="queued", max_length=20)),
                ("stage", models.CharField(default="Queued", max_length=100)),
                ("completed_items", models.PositiveIntegerField(default=0)),
                ("total_items", models.PositiveIntegerField(default=0)),
                ("summary", models.JSONField(default=dict)),
                ("current_attempt_id", models.UUIDField(editable=False, null=True)),
                ("next_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("notification_state", models.CharField(default="pending", max_length=20)),
                ("notification_error", models.TextField(blank=True)),
                ("notification_attempts", models.PositiveSmallIntegerField(default=0)),
                ("notification_due_at", models.DateTimeField(blank=True, null=True)),
                ("notification_token", models.UUIDField(editable=False, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["state", "next_attempt_at"], name="bg_job_state_next_idx"),
                    models.Index(fields=["requester", "-created_at"], name="bg_job_requester_date_idx"),
                    models.Index(fields=["notification_state", "notification_due_at"], name="bg_job_notify_due_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(condition=models.Q(("state__in", ("queued", "running", "retry_wait"))), fields=("requester", "kind"), name="background_one_active_per_user_kind"),
                ],
            },
        ),
        migrations.CreateModel(
            name="JobAttempt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("number", models.PositiveIntegerField()),
                ("cycle_attempt", models.PositiveSmallIntegerField(default=1)),
                ("task_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("state", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("retry_wait", "Waiting to retry"), ("ready", "Ready"), ("partial", "Ready with omissions"), ("failed", "Failed")], default="queued", max_length=20)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("dispatched_at", models.DateTimeField(blank=True, null=True)),
                ("dispatch_after", models.DateTimeField(default=django.utils.timezone.now)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("deadline_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("error", models.TextField(blank=True)),
                ("object_key", models.CharField(blank=True, max_length=500)),
                ("object_version", models.CharField(blank=True, max_length=1024)),
                ("object_deleted_at", models.DateTimeField(blank=True, null=True)),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attempts", to="background_jobs.backgroundjob")),
            ],
            options={
                "ordering": ["number"],
                "indexes": [
                    models.Index(fields=["state", "dispatch_after"], name="bg_attempt_dispatch_idx"),
                    models.Index(fields=["state", "deadline_at"], name="bg_attempt_deadline_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("job", "number"), name="background_unique_attempt"),
                ],
            },
        ),
        migrations.CreateModel(
            name="JobArtifact",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("object_key", models.CharField(max_length=500, unique=True)),
                ("object_version", models.CharField(blank=True, max_length=1024)),
                ("filename", models.CharField(max_length=255)),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("sha256", models.CharField(max_length=64)),
                ("ready_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("delete_error", models.TextField(blank=True)),
                ("attempt", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="artifact", to="background_jobs.jobattempt")),
                ("job", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="artifact", to="background_jobs.backgroundjob")),
            ],
            options={"ordering": ["-ready_at"]},
        ),
    ]
