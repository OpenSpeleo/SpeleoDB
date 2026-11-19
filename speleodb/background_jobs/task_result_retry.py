"""Explicit administrator retries requeue an existing failed task in place."""

from __future__ import annotations

import json
from functools import partial
from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.background_jobs.models import BackgroundJob
from speleodb.background_jobs.models import JobAttempt
from speleodb.background_jobs.operations import _publish
from speleodb.background_jobs.operations import decode_task_arguments
from speleodb.background_jobs.services import GENERATION_TASK
from speleodb.background_jobs.services import NOTIFICATION_TASK
from speleodb.background_jobs.services import dispatch_notification
from speleodb.background_jobs.services import request_notification
from speleodb.background_jobs.services import retry_export
from speleodb.campaigns.operations import TASK_NAME
from speleodb.campaigns.operations import prepare_campaign_retry
from speleodb.common.enums import TaskResultStatus
from speleodb.users.models import LogEntry

if TYPE_CHECKING:
    from speleodb.users.models import User


def retry_task_result(
    result: TaskResult, *, requester: User, site_url: str
) -> list[str]:
    if not requester.is_active or not requester.is_superuser:
        raise PermissionDenied
    with transaction.atomic():
        result = TaskResult.objects.select_for_update().get(pk=result.pk)
        if result.status != TaskResultStatus.FAILURE:
            raise ValueError("Only failed tasks can be retried.")
        if not result.task_name:
            raise ValueError("The original task name is unavailable.")
        task_ids = [result.task_id]
        if result.task_name == GENERATION_TASK:
            attempt = (
                JobAttempt.objects.select_related("job")
                .filter(task_id=result.task_id)
                .first()
            )
            if attempt is None:
                raise ValueError("The original export attempt is unavailable.")
            retry_export(attempt.job, requester, task_id=result.task_id)
        elif result.task_name == NOTIFICATION_TASK:
            args = decode_task_arguments(result.task_args)
            if not isinstance(args, (list, tuple)) or not args:
                raise ValueError("The original notification arguments are unavailable.")
            notification_job = BackgroundJob.objects.filter(pk=args[0]).first()
            if notification_job is None:
                raise ValueError("The original export job is unavailable.")
            request_notification(notification_job, requester)
            dispatch_notification(notification_job.pk, task_id=result.task_id)
        else:
            if result.task_name == TASK_NAME:
                prepare_campaign_retry(result, site_url=site_url)
            args = decode_task_arguments(result.task_args)
            kwargs = decode_task_arguments(result.task_kwargs)
            if not isinstance(args, (list, tuple)) or not isinstance(kwargs, dict):
                raise ValueError("The original task arguments are unavailable.")
            try:
                encoded_args, encoded_kwargs = json.dumps(args), json.dumps(kwargs)
            except TypeError as error:
                raise ValueError(
                    "The task arguments are not JSON serializable."
                ) from error
            metadata = json.loads(result.meta or "{}")
            if not isinstance(metadata, dict):
                raise ValueError("The original task metadata is unavailable.")
            # Keep execution inputs (including refreshed campaign content and force),
            # but none of the previous execution's outcome or publication state.
            for key in (
                "summary",
                "error",
                "error_type",
                "deadline",
                "children",
                "retry_of",
            ):
                metadata.pop(key, None)
            metadata.update(
                requester_id=str(requester.pk),
                stage="awaiting publication",
                publication="unattempted",
            )
            result.task_args = encoded_args
            result.task_kwargs = encoded_kwargs
            result.meta = json.dumps(metadata)
            transaction.on_commit(partial(_publish, task_ids))
        TaskResult.objects.filter(pk=result.pk).update(
            status=TaskResultStatus.PENDING,
            result=None,
            traceback=None,
            date_started=None,
            date_done=timezone.now(),
            worker=None,
            task_args=result.task_args,
            task_kwargs=result.task_kwargs,
            meta=result.meta,
        )
        LogEntry.record(
            actor_email=requester.email,
            action_flag=LogEntry.Action.ACTION,
            obj=result,
            change_message="Requested retry of failed task.",
            details={"task_ids": task_ids},
        )
    return task_ids
