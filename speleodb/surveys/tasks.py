"""Explicit background operations. Failed or interrupted work is rerun manually."""

from __future__ import annotations

from typing import Any

from celery import shared_task
from celery.exceptions import Ignore
from django.conf import settings

from speleodb.background_jobs.operation_execution import operation_execution
from speleodb.gis.geojson_workspaces import geojson_workspace
from speleodb.surveys.models import Project


@shared_task(
    bind=True,
    track_started=False,
    acks_late=False,
    reject_on_worker_lost=False,
    max_retries=0,
    soft_time_limit=settings.GEOJSON_REBUILD_SOFT_TIME_LIMIT,
    time_limit=settings.GEOJSON_REBUILD_HARD_TIME_LIMIT,
)
def refresh_project_geojson(
    self: Any,
    project_id: str,
    *,
    force_recompute: bool = False,
) -> dict[str, Any]:
    with operation_execution(self.request.id) as execution:
        if execution is None:
            raise Ignore
        execution.progress("converting history")
        project = Project.objects.get(pk=project_id)
        summary = project.build_geojsons(force_recompute=force_recompute).as_dict()
        execution.complete(summary)
        return summary


@shared_task(
    bind=True,
    track_started=False,
    acks_late=False,
    reject_on_worker_lost=False,
    max_retries=0,
    soft_time_limit=settings.GEOJSON_REBUILD_SOFT_TIME_LIMIT,
    time_limit=settings.GEOJSON_REBUILD_HARD_TIME_LIMIT,
)
def reset_project_history(self: Any, project_id: str) -> dict[str, Any]:
    with operation_execution(self.request.id) as execution:
        if execution is None:
            raise Ignore
        project = Project.objects.get(pk=project_id)
        summary = project.reset_git_history(progress=execution.progress)
        if not summary["geojson_skipped"]:
            execution.progress("convert_history")
            repository = project.git_repo
            with geojson_workspace(prefix="history-reset-conversion-") as directory:
                summary.update(
                    project.convert_geojson_history(
                        repository,
                        directory,
                        force_recompute=False,
                    ).as_dict()
                )
        execution.complete(summary)
        return summary
