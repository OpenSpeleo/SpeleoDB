"""Repair unnamed accounts before enforcing the name invariant in SQL."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import migrations
from django.db import models

import speleodb.utils.user_identity

if TYPE_CHECKING:
    from django.apps.registry import Apps
    from django.db.backends.base.schema import BaseDatabaseSchemaEditor

# Freeze the repair and constraint policy independently of future runtime edits.
NONBLANK_NAME_PATTERN: str = (
    "[^\t-\r\x1c- \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]"
)


def repair_names(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    user_model = apps.get_model("users", "User")
    user_model.objects.using(schema_editor.connection.alias).exclude(
        name__regex=NONBLANK_NAME_PATTERN
    ).update(name="NO NAME")


class Migration(migrations.Migration):
    dependencies = [("users", "0008_user_has_api_doc_access")]

    operations = [
        migrations.RunPython(repair_names, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="name",
            field=models.CharField(
                max_length=255,
                validators=[speleodb.utils.user_identity.validate_user_name],
                verbose_name="Name of User",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(name__regex=NONBLANK_NAME_PATTERN),
                name="users_user_name_nonblank",
            ),
        ),
    ]
