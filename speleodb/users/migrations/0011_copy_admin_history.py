"""Preserve every existing admin entry before switching the active audit table."""

from __future__ import annotations

from itertools import batched
from typing import TYPE_CHECKING

from django.core.management.color import no_style
from django.db import migrations

if TYPE_CHECKING:
    from django.apps.registry import Apps
    from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def copy_admin_history(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    source_model = apps.get_model("admin", "LogEntry")
    destination_model = apps.get_model("users", "LogEntry")
    database = schema_editor.connection.alias
    source = (
        source_model.objects.using(database)
        .select_related("user", "content_type")
        .order_by("pk")
    )
    for batch in batched(source.iterator(chunk_size=1000), 1000):
        destination_model.objects.using(database).bulk_create(
            [
                destination_model(
                    pk=entry.pk,
                    action_time=entry.action_time,
                    actor_email=entry.user.email,
                    model_label=(
                        f"{entry.content_type.app_label}.{entry.content_type.model}"
                        if entry.content_type is not None
                        else ""
                    ),
                    object_id=entry.object_id,
                    object_repr=entry.object_repr,
                    action_flag=entry.action_flag,
                    change_message=entry.change_message,
                    details={},
                )
                for entry in batch
            ]
        )
    with schema_editor.connection.cursor() as cursor:
        for statement in schema_editor.connection.ops.sequence_reset_sql(
            no_style(), [destination_model]
        ):
            cursor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0010_logentry"),
        ("admin", "0003_logentry_add_action_flag_choices"),
    ]

    # Reversing the cutover must not silently discard new permanent audit rows.
    operations = [migrations.RunPython(copy_admin_history)]
