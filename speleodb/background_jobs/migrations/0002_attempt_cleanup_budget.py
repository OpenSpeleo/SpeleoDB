from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [("background_jobs", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="jobattempt",
            name="dispatch_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="jobattempt",
            name="cleanup_attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="jobattempt",
            name="cleanup_due_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="jobattempt",
            name="cleanup_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="jobattempt",
            name="cleanup_token",
            field=models.UUIDField(editable=False, null=True),
        ),
    ]
