# -*- coding: utf-8 -*-

from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('surveys', '0031_update_teampermission_for_uuid_teams'),
        ('users', '0005_convert_surveyteam_to_uuid'),
    ]

    operations = [
        # # ================================ CLEANUP  ================================ #
        # Step 1: Remove the old field
        migrations.RemoveField(
            model_name='teampermission',
            name='target',
        ),

        # Step 2: Rename the field
        migrations.RenameField(
            model_name='teampermission',
            old_name='target_uuid',
            new_name='target',
        ),

        # Step 3: Restore FK constraint
        migrations.AlterField(
            model_name='teampermission',
            name='target',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rel_permissions', to='users.surveyteam'),
        ),

        # Step 4: Restore unique constraint
        migrations.AlterUniqueTogether(
            name='teampermission',
            unique_together={('target', 'project')},
        ),
    ]
