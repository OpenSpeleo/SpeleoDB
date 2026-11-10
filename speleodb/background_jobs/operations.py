"""Validate and publish immediate operations, with Celery recording their results."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING
from typing import Any
from uuid import UUID
from uuid import uuid4

from celery import current_app
from celery.result import GroupResult as CeleryGroupResult
from django.conf import settings
from django.contrib.admin.models import CHANGE
from django.contrib.admin.models import LogEntry
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.common.enums import ProjectType
from speleodb.common.enums import TaskResultStatus
from speleodb.surveys.models import Project

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from speleodb.surveys.models import ProjectCommit
    from speleodb.users.models import User

logger = logging.getLogger(__name__)
SUPPORTED_TYPES = (ProjectType.ARIANE, ProjectType.COMPASS, ProjectType.STALAGMIGHT)
TASK_NAMES = {
    "history": "speleodb.surveys.tasks.reset_project_history",
    "project": "speleodb.surveys.tasks.refresh_project_geojson",
    "upload": "speleodb.gis.tasks.generate_project_geojson",
}


@dataclass(frozen=True)
class OperationReceipt:
    task_ids: list[str]
    group_id: str | None = None


def eligible_projects() -> QuerySet[Project]:
    return Project.objects.filter(exclude_geojson=False, type__in=SUPPORTED_TYPES)


def get_operation_parameters(result: TaskResult) -> dict[str, Any]:
    try:
        metadata = json.loads(result.meta or "{}")
        if not isinstance(metadata, dict):
            raise TypeError("Invalid operation metadata.")  # noqa: TRY301
        operation = metadata.get("operation")
        if (
            operation not in {"history", "project"}
            or result.task_name != TASK_NAMES[operation]
        ):
            raise ValueError("This task does not support manual reruns.")
        project_id = str(UUID(metadata["project_id"]))
        force = metadata.get("force", False)
        if not isinstance(force, bool):
            raise TypeError("Invalid force setting.")  # noqa: TRY301
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Invalid operation metadata.") from error
    return {"operation": operation, "project_id": project_id, "force": force}


def receipt_task_ids(group_id: str) -> list[str]:
    group = CeleryGroupResult.restore(str(UUID(group_id)), app=current_app)
    if group is None:
        raise ValueError("The task group is unavailable or has expired.")
    return [result.id for result in (group.results or [])]


def _publish(task_ids: list[str]) -> None:
    """Never retry uncertain publication: a timeout may follow broker acceptance."""
    for task_id in task_ids:
        try:
            result = TaskResult.objects.get(task_id=task_id)
            metadata = json.loads(result.meta or "{}")
            if metadata.get("publication") != "unattempted":
                continue
            kwargs = json.loads(result.task_kwargs or "{}")
            # Record uncertainty before external I/O. A killed publisher must
            # not leave an accepted message labelled as never submitted.
            metadata.update(publication="ambiguous", stage="submission unconfirmed")
            updated = TaskResult.objects.filter(
                task_id=task_id, status=TaskResultStatus.PENDING, meta=result.meta
            ).update(meta=json.dumps(metadata))
            if not updated:
                continue
        except Exception:
            logger.exception("Could not prepare operations publication %s", task_id)
            break
        try:
            current_app.send_task(
                result.task_name,
                args=json.loads(result.task_args or "[]"),
                kwargs=kwargs,
                task_id=task_id,
                queue="background_control",
                headers={"meta": {**metadata, "publication": "confirmed"}},
                retry=False,
            )
        except Exception:
            logger.exception(
                "Could not confirm publication of operations task %s", task_id
            )
            # Remaining rows stay explicitly unattempted. Manual recovery never
            # republishes one of these IDs; it creates a fresh execution.
            break
        try:
            metadata.update(publication="confirmed", stage="queued")
            TaskResult.objects.filter(
                task_id=task_id, status=TaskResultStatus.PENDING
            ).update(meta=json.dumps(metadata))
        except Exception:
            # Publication may have succeeded. Retain uncertainty and source-save
            # success even if the confirmation's database write is unavailable.
            logger.exception("Could not record confirmed publication %s", task_id)
            break


def _create_task(
    project: Project,
    operation: str,
    *,
    force: bool,
    requester: User | None,
    revision: str | None = None,
) -> str:
    task_id = str(uuid4())
    args = [revision if operation == "upload" else str(project.pk)]
    kwargs: dict[str, Any] = {}
    if operation == "project":
        kwargs["force_recompute"] = force
    metadata = {
        "operation": operation,
        "project_id": str(project.pk),
        "project_name": project.name,
        "requester_id": str(requester.pk) if requester else None,
        "force": force,
        "revision": revision,
        "stage": "awaiting publication",
        "publication": "unattempted",
        "deadline": (
            timezone.now()
            + timedelta(
                seconds=(
                    settings.GEOJSON_GENERATION_HARD_TIME_LIMIT
                    if operation == "upload"
                    else settings.GEOJSON_REBUILD_HARD_TIME_LIMIT
                )
            )
        ).isoformat(),
    }
    TaskResult.objects.create(
        task_id=task_id,
        task_name=TASK_NAMES[operation],
        status=TaskResultStatus.PENDING,
        task_args=json.dumps(args),
        task_kwargs=json.dumps(kwargs),
        content_type="application/json",
        content_encoding="utf-8",
        meta=json.dumps(metadata),
    )
    if requester is not None:
        LogEntry.objects.log_actions(
            user_id=requester.pk,
            queryset=Project.objects.filter(pk=project.pk),
            action_flag=CHANGE,
            change_message=json.dumps(
                {"operation": operation, "task_id": task_id, "force": force}
            ),
        )
    return task_id


def schedule_operation(
    operation: str,
    *,
    requester: User,
    project_id: UUID | str | None = None,
    force: bool = False,
) -> OperationReceipt:
    if not requester.is_active or not requester.is_superuser:
        raise PermissionDenied
    if operation not in {"history", "project", "all"}:
        raise ValueError("Unsupported operation.")
    if not isinstance(force, bool):
        raise TypeError("Invalid force setting.")
    with transaction.atomic():
        if operation == "all":
            if project_id is not None:
                raise ValueError("Global recomputation does not accept a project.")
            projects = eligible_projects().order_by("pk")
        else:
            selected = Project.objects.get(pk=UUID(str(project_id)))
            if (
                operation == "project"
                and not eligible_projects().filter(pk=selected.pk).exists()
            ):
                raise ValueError("This project does not support GeoJSON generation.")
            projects = Project.objects.filter(pk=selected.pk)
        task_ids = [
            _create_task(
                project,
                "project" if operation == "all" else operation,
                force=force,
                requester=requester,
            )
            for project in projects.iterator()
        ]
        group_id = str(uuid4()) if operation == "all" else None
        if group_id is not None:
            CeleryGroupResult(
                group_id,
                [current_app.AsyncResult(task_id) for task_id in task_ids],
                app=current_app,
            ).save()
        transaction.on_commit(lambda: _publish(task_ids))
    return OperationReceipt(task_ids, group_id)


def schedule_uploaded_geojson(project: Project, commit: ProjectCommit) -> None:
    if not eligible_projects().filter(pk=project.pk).exists():
        return
    with transaction.atomic():
        task_id = _create_task(
            project, "upload", force=False, requester=None, revision=commit.pk
        )
        transaction.on_commit(lambda: _publish([task_id]))
