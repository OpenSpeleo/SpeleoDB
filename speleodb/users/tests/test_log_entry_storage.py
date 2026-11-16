"""Administrator history survives removal of its actor and target."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from celery import current_app
from django.contrib.auth.models import Group
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.common.enums import TaskResultStatus
from speleodb.users.models import LogEntry
from speleodb.users.models import User
from speleodb.users.tests.factories import UserFactory


@pytest.mark.django_db
def test_admin_history_survives_actor_deletion() -> None:
    actor: User = UserFactory.create(is_staff=True, is_superuser=True)
    actor_email: str = actor.email
    target: Group = Group.objects.create(name="Audit retention target")
    entry = LogEntry.record(
        actor_email=actor.email,
        obj=target,
        action_flag=LogEntry.Action.CHANGE,
        change_message="Changed group name.",
    )

    actor.email = "renamed-audit-actor@example.com"
    actor.save(update_fields=["email"])
    actor.delete()

    entry.refresh_from_db()
    assert entry.actor_email == actor_email
    assert entry.change_message == "Changed group name."


@pytest.mark.django_db
def test_admin_history_survives_target_deletion() -> None:
    target: Group = Group.objects.create(name="Removed audit target")
    target_id: str = str(target.pk)
    entry = LogEntry.record(
        actor_email="administrator@example.com",
        obj=target,
        action_flag=LogEntry.Action.DELETION,
    )

    target.delete()

    entry.refresh_from_db()
    assert entry.model_label == "auth.group"
    assert entry.object_id == target_id
    assert entry.object_repr == "Removed audit target"


@pytest.mark.django_db
def test_technical_result_expiration_preserves_old_admin_history() -> None:
    old_timestamp = timezone.now() - timedelta(days=365)
    entry = LogEntry.record(
        actor_email="administrator@example.com",
        action_flag=LogEntry.Action.ACTION,
        change_message="Requested GeoJSON recomputation.",
    )
    LogEntry.objects.filter(pk=entry.pk).update(action_time=old_timestamp)
    result = TaskResult.objects.create(
        task_id=str(uuid4()), status=TaskResultStatus.SUCCESS
    )
    TaskResult.objects.filter(pk=result.pk).update(date_done=old_timestamp)

    current_app.backend.cleanup()

    assert not TaskResult.objects.filter(pk=result.pk).exists()
    entry.refresh_from_db()
    assert entry.action_time == old_timestamp
