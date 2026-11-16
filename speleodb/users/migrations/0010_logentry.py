"""Store administrator history independently of user and target lifetimes."""

from django.db import migrations
from django.db import models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [("users", "0009_require_user_name")]

    operations = [
        migrations.CreateModel(
            name="LogEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "action_time",
                    models.DateTimeField(default=timezone.now, editable=False),
                ),
                ("actor_email", models.EmailField(max_length=254)),
                ("model_label", models.CharField(blank=True, max_length=255)),
                ("object_id", models.TextField(blank=True, null=True)),
                ("object_repr", models.CharField(max_length=200)),
                (
                    "action_flag",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Addition"),
                            (2, "Change"),
                            (3, "Deletion"),
                            (4, "Action"),
                        ]
                    ),
                ),
                ("change_message", models.TextField(blank=True)),
                ("details", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "verbose_name": "log entry",
                "verbose_name_plural": "log entries",
                "ordering": ["-action_time", "-id"],
                "indexes": [
                    models.Index(
                        fields=["-action_time", "-id"], name="admin_audit_time_idx"
                    ),
                    models.Index(
                        fields=["actor_email", "-action_time"],
                        name="admin_audit_actor_idx",
                    ),
                    models.Index(
                        fields=["model_label", "object_id"],
                        name="admin_audit_object_idx",
                    ),
                ],
            },
        ),
    ]
