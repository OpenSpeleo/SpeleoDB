# -*- coding: utf-8 -*-

import uuid
from django.db import migrations, models
import django.db.models.deletion


def generate_uuids(apps, schema_editor):
    SurveyTeam = apps.get_model('users', 'SurveyTeam')
    for obj in SurveyTeam.objects.all():
        obj.uuid_id = uuid.uuid4()
        obj.save(update_fields=["uuid_id"])


class Migration(migrations.Migration):

    dependencies = [
        ('surveys', '0031_update_teampermission_for_uuid_teams'),
        ('users', '0004_alter_surveyteammembership_deactivated_by'),
    ]

    operations = [
        # ================================ Temporary Fields  ================================ #
        # Step 1: Break the unique constraint to allow changes
        migrations.AlterUniqueTogether(
            name='surveyteammembership',
            unique_together=set(),
        ),

        # Step 2: Add UUID fields alongside existing integer fields
        migrations.AddField(
            model_name='surveyteam',
            name='uuid_id',
            field=models.UUIDField(null=True, unique=True),
        ),
        migrations.RunPython(generate_uuids),  # Necessary to populate the new UUID field
        migrations.AlterField(
            model_name='surveyteam',
            name='uuid_id',
            field=models.UUIDField(unique=True),  # Now enforce non-null
        ),

        migrations.AddField(
            model_name='surveyteammembership',
            name='team_uuid',
            field=models.UUIDField(null=True),
        ),
        
        # Step 3: Drop FK Constraint
        migrations.AlterField(
            model_name='surveyteammembership',
            name='team',
            field=models.IntegerField(),
        ),

        # # ================================ MIGRATION  ================================ #
        migrations.RunSQL(
            sql="""
            -- Update foreign key references to match
            UPDATE users_surveyteammembership
            SET team_uuid = st.uuid_id
            FROM users_surveyteam st
            WHERE users_surveyteammembership.team = st.id;
            """
        ),
        migrations.RunSQL(
            sql="""
            -- Map target_id (integer) to target_uuid using the new uuid_id field
            UPDATE surveys_teampermission
            SET target_uuid = st.uuid_id
            FROM users_surveyteam st
            WHERE surveys_teampermission.target = st.id;
            """,
        ),
        # ================================ CLEANUP  ================================ #
        # Step 1: Remove the old fields
        migrations.RemoveField(
            model_name='surveyteam',
            name='id',
        ),
        migrations.RemoveField(
            model_name='surveyteammembership',
            name='team',
        ),

        # Step 2: Rename the fields
        migrations.RenameField(
            model_name='surveyteam',
            old_name='uuid_id',
            new_name='id',
        ),
        migrations.RenameField(
            model_name='surveyteammembership',
            old_name='team_uuid',
            new_name='team',
        ),

        # Step 3: Restore the primary key
        migrations.AlterField(
            model_name='surveyteam',
            name='id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
        ),

        # Step 4: Restore FK constraint
        migrations.AlterField(
            model_name='surveyteammembership',
            name='team',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rel_team_memberships', to='users.surveyteam'),
        ),

        # Step 4: Restore unique constraint
        migrations.AlterUniqueTogether(
            name='surveyteammembership',
            unique_together={("user", "team")},
        ),
    ]
