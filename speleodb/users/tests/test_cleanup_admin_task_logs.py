"""Noise cleanup is explicit, conservative and never audits its own deletion."""

from __future__ import annotations

import json
from io import StringIO
from typing import Any
from uuid import uuid4

import pytest
from django.core.management import call_command

from speleodb.users.models import LogEntry


def _entry(
    message: str | dict[str, Any],
    *,
    action_flag: int = LogEntry.Action.CHANGE,
    model_label: str = "surveys.project",
) -> LogEntry:
    return LogEntry.objects.create(
        actor_email="administrator@example.com",
        action_flag=action_flag,
        model_label=model_label,
        object_id=str(uuid4()),
        object_repr="Historical project",
        change_message=json.dumps(message) if isinstance(message, dict) else message,
    )


@pytest.mark.django_db
def test_cleanup_preserves_admin_actions_and_unknown_messages() -> None:
    outcome: dict[str, Any] = {
        "task_id": str(uuid4()),
        "operation": "project",
        "stage": "completed",
        "summary": {"generated": 1},
    }
    completed = _entry(outcome)
    failed = _entry(
        {**outcome, "operation": "history", "stage": "failed", "summary": None}
    )
    preserved = [
        _entry({"task_id": str(uuid4()), "operation": "project", "force": True}),
        _entry("Changed project name."),
        _entry('{"stage": "completed"'),
        _entry({**outcome, "task_id": "not-a-task-id"}),
        _entry({**outcome, "operation": "unknown-operation"}),
        _entry({**outcome, "stage": "queued"}),
        _entry({**outcome, "extra": "unrecognized format"}),
        _entry({**outcome, "summary": "unrecognized summary"}),
        _entry(outcome, action_flag=LogEntry.Action.ACTION),
        _entry(outcome, model_label="users.user"),
    ]
    before = list(LogEntry.objects.order_by("pk").values())
    preview = StringIO()

    call_command("cleanup_admin_task_logs", "--dry-run", stdout=preview)

    assert list(LogEntry.objects.order_by("pk").values()) == before
    assert f'"id": {completed.pk}' in preview.getvalue()
    assert f'"id": {failed.pk}' in preview.getvalue()
    assert "Dry run: 2" in preview.getvalue()
    default_preview = StringIO()
    call_command("cleanup_admin_task_logs", stdout=default_preview)
    assert list(LogEntry.objects.order_by("pk").values()) == before
    assert default_preview.getvalue() == preview.getvalue()

    applied = StringIO()
    call_command("cleanup_admin_task_logs", "--apply", stdout=applied)

    assert "Deleted 2" in applied.getvalue()
    assert set(LogEntry.objects.values_list("pk", flat=True)) == {
        entry.pk for entry in preserved
    }
    after = list(LogEntry.objects.order_by("pk").values())
    call_command("cleanup_admin_task_logs", "--apply", stdout=StringIO())
    assert list(LogEntry.objects.order_by("pk").values()) == after
