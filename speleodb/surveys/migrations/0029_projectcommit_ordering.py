from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("surveys", "0028_alter_project_color")]

    operations = [
        migrations.AlterModelOptions(
            name="projectcommit",
            options={
                "ordering": ("-authored_date", "-creation_date", "-id"),
                "verbose_name": "Project Commit",
                "verbose_name_plural": "Project Commits",
            },
        ),
    ]
