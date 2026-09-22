import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("gis", "0041_gis_geometry"),
        ("surveys", "0028_alter_project_color"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectGeoJSONGeneration",
            fields=[
                (
                    "commit",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="geojson_generation",
                        serialize=False,
                        to="surveys.projectcommit",
                    ),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("ready", "Ready"),
                            ("skipped", "Skipped"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=12,
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("dispatch_attempts", models.PositiveIntegerField(default=0)),
                (
                    "next_attempt_at",
                    models.DateTimeField(
                        blank=True, default=django.utils.timezone.now, null=True
                    ),
                ),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("lease_expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_error_code", models.CharField(blank=True, max_length=40)),
                ("last_error", models.CharField(blank=True, max_length=2000)),
                (
                    "unpublished_objects",
                    models.JSONField(default=list, blank=True, editable=False),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now, editable=False
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now, editable=False
                    ),
                ),
            ],
            options={
                "verbose_name": "Project GeoJSON generation",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["state", "next_attempt_at"], name="gis_geojson_due_idx"
                    ),
                    models.Index(
                        fields=["state", "lease_expires_at"],
                        name="gis_geojson_lease_idx",
                    ),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name="projectgeojson",
            options={
                "ordering": [
                    "-commit__authored_date",
                    "-commit__creation_date",
                    "-commit_id",
                ],
                "verbose_name": "Project GeoJSON",
                "verbose_name_plural": "Project GeoJSONs",
            },
        ),
    ]
