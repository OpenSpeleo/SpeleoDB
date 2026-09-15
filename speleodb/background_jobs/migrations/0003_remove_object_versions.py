from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("background_jobs", "0002_attempt_cleanup_budget")]

    operations = [
        migrations.RemoveField(model_name="jobattempt", name="object_version"),
        migrations.RemoveField(model_name="jobartifact", name="object_version"),
    ]
