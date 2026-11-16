"""The cutover preserves historical audit content and subsequent inserts."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

import django.contrib.admin.models
import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.migrations.loader import MigrationLoader

from speleodb.users.models import LogEntry
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.users.models import User

migration_module = import_module("speleodb.users.migrations.0011_copy_admin_history")


@pytest.mark.django_db(transaction=True)
def test_copy_preserves_all_history_and_resets_insert_sequence() -> None:
    actor: User = UserFactory.create(is_staff=True, is_superuser=True)
    content_type: ContentType = ContentType.objects.get_for_model(actor)
    message: str = '[{"changed": {"fields": ["name"]}}]'
    original = django.contrib.admin.models.LogEntry.objects.create(
        pk=7001,
        user=actor,
        content_type=content_type,
        object_id=str(actor.pk),
        object_repr="Original account representation",
        action_flag=django.contrib.admin.models.CHANGE,
        change_message=message,
    )
    unknown_target = django.contrib.admin.models.LogEntry.objects.create(
        pk=7002,
        user=actor,
        object_id="removed-object",
        object_repr="Removed content type",
        action_flag=django.contrib.admin.models.DELETION,
        change_message="Unstructured historical message.",
    )
    historical_apps = (
        MigrationLoader(connection)
        .project_state([("users", "0011_copy_admin_history")])
        .apps
    )
    with connection.schema_editor() as schema_editor:
        migration_module.copy_admin_history(historical_apps, schema_editor)

    copied = LogEntry.objects.get(pk=original.pk)
    assert set(LogEntry.objects.values_list("pk", flat=True)) == {
        original.pk,
        unknown_target.pk,
    }
    assert copied.action_time == original.action_time
    assert copied.actor_email == actor.email
    assert copied.model_label == "users.user"
    assert copied.object_id == original.object_id
    assert copied.object_repr == original.object_repr
    assert copied.action_flag == original.action_flag
    assert copied.change_message == message
    assert copied.get_change_message() == "Changed name."
    unknown_copy = LogEntry.objects.get(pk=unknown_target.pk)
    assert unknown_copy.model_label == ""
    assert unknown_copy.change_message == unknown_target.change_message
    assert unknown_copy.object_repr == unknown_target.object_repr
    assert set(
        django.contrib.admin.models.LogEntry.objects.values_list("pk", flat=True)
    ) == {
        original.pk,
        unknown_target.pk,
    }

    next_entry = LogEntry.record(
        actor_email=actor.email,
        action_flag=LogEntry.Action.ACTION,
        change_message="Requested a new operation.",
    )
    assert next_entry.pk > unknown_target.pk
