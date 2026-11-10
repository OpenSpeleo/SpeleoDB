"""Dispatch submitted work through a worker or the configured immediate backend."""

from __future__ import annotations

from typing import Any

from celery import current_app


def dispatch_task(
    name: str,
    *,
    args: list[Any],
    queue: str,
    kwargs: dict[str, Any] | None = None,
    task_id: str | None = None,
    headers: dict[str, Any] | None = None,
) -> None:
    if current_app.conf.task_always_eager:
        # Web startup does not load task modules, and send_task ignores eager mode.
        current_app.autodiscover_tasks(force=True)
        current_app.tasks[name].apply(
            args=tuple(args),
            kwargs=kwargs,
            task_id=task_id,
            headers=headers,
            throw=False,
        )
        return
    current_app.send_task(
        name,
        args=args,
        kwargs=kwargs,
        task_id=task_id,
        queue=queue,
        headers=headers,
        retry=False,
    )
