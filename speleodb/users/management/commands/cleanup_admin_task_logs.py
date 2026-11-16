"""Explicitly remove only the historical worker-outcome audit noise."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand
from django.db import transaction

from speleodb.users.models import LogEntry

if TYPE_CHECKING:
    from django.core.management.base import CommandParser


def is_historical_worker_outcome(entry: LogEntry) -> bool:
    if (
        entry.model_label != "surveys.project"
        or entry.action_flag != LogEntry.Action.CHANGE
    ):
        return False
    try:
        message: Any = json.loads(entry.change_message)
    except ValueError:
        return False
    if not isinstance(message, dict) or set(message) != {
        "task_id",
        "operation",
        "stage",
        "summary",
    }:
        return False
    if (
        message["operation"] not in ("project", "history")
        or message["stage"] not in ("completed", "failed")
        or not isinstance(message["task_id"], str)
        or (message["summary"] is not None and not isinstance(message["summary"], dict))
    ):
        return False
    try:
        return str(UUID(message["task_id"])) == message["task_id"]
    except ValueError:
        return False


class Command(BaseCommand):
    help = (
        "Preview historical Project worker-outcome log entries. "
        "Use --apply to delete the exact recognized records "
        "without creating audit entries."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument(
            "--dry-run",
            action="store_true",
            help="Report candidates without changing records (the default).",
        )
        mode.add_argument(
            "--apply",
            action="store_true",
            help="Delete the recognized historical noise.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        candidate_ids: list[int] = []
        for entry in (
            LogEntry.objects.filter(
                model_label="surveys.project", action_flag=LogEntry.Action.CHANGE
            )
            .order_by("pk")
            .iterator()
        ):
            if is_historical_worker_outcome(entry):
                candidate_ids.append(entry.pk)
                self.stdout.write(
                    json.dumps(
                        {
                            "id": entry.pk,
                            "action_time": entry.action_time.isoformat(),
                            "actor_email": entry.actor_email,
                            "object_id": entry.object_id,
                            "object_repr": entry.object_repr,
                            "change_message": entry.change_message,
                        }
                    )
                )
        if options["apply"]:
            deleted, _ = LogEntry.objects.filter(pk__in=candidate_ids).delete()
            self.stdout.write(f"Deleted {deleted} historical worker-outcome entries.")
        else:
            self.stdout.write(
                f"Dry run: {len(candidate_ids)} historical worker-outcome entries; "
                "no records changed."
            )
