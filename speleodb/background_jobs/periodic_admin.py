"""Audit explicit schedule administration independently of scheduled execution."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from uuid import uuid4

import django_celery_beat.admin
from django.contrib import admin
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django_celery_beat.models import PeriodicTask
from kombu.utils.json import loads

from speleodb.users.models import LogEntry

if TYPE_CHECKING:
    from celery.app.task import Task
    from django.db.models import QuerySet
    from django.http import HttpRequest

    from speleodb.users.models import User

logger = logging.getLogger(__name__)


class PeriodicTaskAdmin(django_celery_beat.admin.PeriodicTaskAdmin):
    """Keep upstream schedule mutations while recording their actual changes."""

    @admin.action(description="Enable selected tasks")
    @transaction.atomic
    def enable_tasks(
        self, request: HttpRequest, queryset: QuerySet[PeriodicTask]
    ) -> None:
        changed = list(queryset.filter(enabled=False))
        super().enable_tasks(  # type: ignore[no-untyped-call]  # Upstream admin has no method annotations.
            request, queryset.filter(pk__in=[task.pk for task in changed])
        )
        for task in changed:
            self.log_change(request, task, "Enabled scheduled task.")

    @admin.action(description="Disable selected tasks")
    @transaction.atomic
    def disable_tasks(
        self, request: HttpRequest, queryset: QuerySet[PeriodicTask]
    ) -> None:
        changed = list(queryset.filter(Q(enabled=True) | Q(last_run_at__isnull=False)))
        super().disable_tasks(  # type: ignore[no-untyped-call]  # Upstream admin has no method annotations.
            request, queryset.filter(pk__in=[task.pk for task in changed])
        )
        for task in changed:
            self.log_change(
                request, task, "Disabled scheduled task and cleared its last run."
            )

    @admin.action(description="Toggle activity of selected tasks")
    @transaction.atomic
    def toggle_tasks(
        self, request: HttpRequest, queryset: QuerySet[PeriodicTask]
    ) -> None:
        changed = list(queryset)
        super().toggle_tasks(request, queryset)  # type: ignore[no-untyped-call]  # Upstream admin has no method annotations.
        for task in changed:
            message = (
                "Disabled scheduled task."
                if task.enabled
                else "Enabled scheduled task."
            )
            self.log_change(request, task, message)

    @admin.action(description="Run selected tasks")
    def run_tasks(self, request: HttpRequest, queryset: QuerySet[PeriodicTask]) -> None:
        self.celery_app.loader.import_default_modules()
        schedules = list(queryset)
        submissions: list[
            tuple[Task[Any, Any], list[Any], dict[str, Any], str | None, str, str]
        ] = []
        for schedule in schedules:
            task = self.celery_app.tasks.get(schedule.task)
            if task is None:
                self.message_user(
                    request, f'Task "{schedule.task}" not found.', messages.ERROR
                )
                return
            try:
                args = loads(schedule.args)
                kwargs = loads(schedule.kwargs)
            except ValueError, TypeError:
                self.message_user(
                    request,
                    f'Task "{schedule.name}" has invalid arguments.',
                    messages.ERROR,
                )
                return
            if not isinstance(args, list) or not isinstance(kwargs, dict):
                self.message_user(
                    request,
                    f'Task "{schedule.name}" has invalid arguments.',
                    messages.ERROR,
                )
                return
            submissions.append(
                (task, args, kwargs, schedule.queue, schedule.name, str(uuid4()))
            )
        if not submissions:
            return

        def publish() -> None:
            submitted = 0
            for task, args, kwargs, queue, name, task_id in submissions:
                try:
                    options: dict[str, Any] = {
                        "task_id": task_id,
                        "headers": {"periodic_task_name": name},
                    }
                    if queue:
                        options["queue"] = queue
                    task.apply_async(args=tuple(args), kwargs=kwargs, **options)
                except Exception:
                    logger.exception(
                        "Could not confirm manual schedule publication %s", task_id
                    )
                    self.message_user(
                        request,
                        f"Submitted {submitted} task(s); submission of {task_id} "
                        "is unconfirmed. Remaining tasks were not submitted. "
                        "Review worker activity before rerunning.",
                        messages.ERROR,
                    )
                    return
                submitted += 1
            self.message_user(
                request, f"Submitted {submitted} task(s) for manual execution."
            )

        with transaction.atomic():
            LogEntry.record(
                actor_email=cast("User", request.user).email,
                action_flag=LogEntry.Action.ACTION,
                model_label=PeriodicTask._meta.label_lower,  # noqa: SLF001
                object_repr=f"{len(schedules)} scheduled task(s)",
                change_message=(
                    f"Requested manual execution of {len(schedules)} scheduled task(s)."
                ),
                details={
                    "operation": "run_scheduled_tasks",
                    "targets": [
                        {
                            "id": str(schedule.pk),
                            "name": schedule.name,
                            "task": schedule.task,
                        }
                        for schedule in schedules
                    ],
                    "task_ids": [submission[-1] for submission in submissions],
                },
            )
            transaction.on_commit(publish)


admin.site.unregister(PeriodicTask)
admin.site.register(PeriodicTask, PeriodicTaskAdmin)
