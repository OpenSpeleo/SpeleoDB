"""Single-delivery execution and outcomes in Celery's result row."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING
from typing import Any

from celery import current_app
from celery import current_task
from django.conf import settings
from django.contrib.admin.models import CHANGE
from django.contrib.admin.models import LogEntry
from django.db import transaction
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.common.enums import TaskResultStatus
from speleodb.surveys.models import Project

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)


@dataclass
class OperationExecution:
    task_id: str
    metadata: dict[str, Any]

    def progress(self, stage: str, **counts: Any) -> None:
        self.metadata.update(stage=stage, **counts)
        if current_task:
            setattr(current_task.request, "meta", self.metadata)  # noqa: B010 - Celery extension metadata.
        TaskResult.objects.filter(task_id=self.task_id).update(
            meta=json.dumps(self.metadata), date_done=timezone.now()
        )

    def audit_outcome(self) -> None:
        requester_id = self.metadata.get("requester_id")
        if requester_id is not None:
            LogEntry.objects.log_actions(
                user_id=requester_id,
                queryset=Project.objects.filter(pk=self.metadata["project_id"]),
                action_flag=CHANGE,
                change_message=json.dumps(
                    {
                        "task_id": self.task_id,
                        "operation": self.metadata["operation"],
                        "stage": self.metadata["stage"],
                        "summary": self.metadata.get("summary"),
                    }
                ),
            )

    def complete(self, summary: dict[str, Any]) -> None:
        self.progress("completed", summary=summary)
        self.audit_outcome()
        TaskResult.objects.filter(task_id=self.task_id).update(
            status=TaskResultStatus.SUCCESS, result=json.dumps(summary)
        )


@contextmanager
def operation_execution(task_id: str) -> Iterator[OperationExecution | None]:
    """Claim only a precreated pending row; duplicate deliveries cannot execute."""
    with transaction.atomic():
        result = TaskResult.objects.select_for_update().filter(task_id=task_id).first()
        if result is None or result.status != TaskResultStatus.PENDING:
            execution = None
        else:
            metadata = json.loads(result.meta or "{}")
            now = timezone.now()
            metadata["deadline"] = (
                now
                + timedelta(
                    seconds=(
                        settings.GEOJSON_GENERATION_HARD_TIME_LIMIT
                        if metadata.get("operation") == "upload"
                        else settings.GEOJSON_REBUILD_HARD_TIME_LIMIT
                    )
                )
            ).isoformat()
            metadata["stage"] = "started"
            metadata["publication"] = "confirmed"
            result.status = TaskResultStatus.STARTED
            result.date_started = now  # type: ignore[attr-defined]  # Upstream field missing in stubs.
            result.meta = json.dumps(metadata)
            result.save(update_fields=["status", "date_started", "meta", "date_done"])
            execution = OperationExecution(task_id, metadata)
    if execution is None:
        yield None
        return
    execution.progress("started")
    try:
        yield execution
    except Exception as error:
        summary: Any = getattr(error, "summary", None)
        if hasattr(summary, "as_dict"):
            summary = summary.as_dict()
        execution.progress(
            "failed",
            error="The operation failed. Review the task result and worker traceback.",
            error_type=type(error).__name__,
            **({"summary": summary} if isinstance(summary, dict) else {}),
        )
        # Status and encoded failure must become visible together. A Celery
        # client can read this row before the worker's final backend write.
        failure = current_app.backend.prepare_exception(error, serializer="json")
        TaskResult.objects.filter(task_id=task_id).update(
            status=TaskResultStatus.FAILURE, result=json.dumps(failure)
        )
        execution.audit_outcome()
        logger.exception("Operation %s failed", task_id)
        raise
