# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TypedDict

from celery import shared_task
from django.conf import settings
from django.core.management import call_command

from speleodb.surveys.models import Project

logger = logging.getLogger(__name__)


class EnqueuedProjectRebuild(TypedDict):
    project_id: str
    task_id: str


class ProjectRebuildBatch(TypedDict):
    enqueued: int
    tasks: list[EnqueuedProjectRebuild]


@shared_task(
    soft_time_limit=settings.GEOJSON_REBUILD_SOFT_TIME_LIMIT,
    time_limit=settings.GEOJSON_REBUILD_HARD_TIME_LIMIT,
)
def refresh_project_geojson(project_id: str, *, force_recompute: bool = False) -> str:
    """Rebuild one project's history in an isolated, disposable disk workspace."""
    if not Project.objects.filter(id=project_id, exclude_geojson=False).exists():
        logger.info("Skipping deleted or excluded GeoJSON project %s", project_id)
        return "skipped"
    call_command(
        "build_project_geojsons",
        project_id=project_id,
        force_recompute=force_recompute,
    )
    return "completed"


@shared_task()
def refresh_all_projects_geojson() -> ProjectRebuildBatch:
    """Enqueue one forced history rebuild per eligible project without waiting."""
    tasks: list[EnqueuedProjectRebuild] = []
    project_ids = (
        Project.objects.filter(exclude_geojson=False)
        .order_by("-modified_date", "id")
        .values_list("id", flat=True)
        .iterator()
    )
    for project_id in project_ids:
        result = refresh_project_geojson.apply_async(
            args=(str(project_id),),
            kwargs={"force_recompute": True},
            retry=False,
        )
        tasks.append({"project_id": str(project_id), "task_id": result.id})
        logger.info(
            "Enqueued forced GeoJSON rebuild for project %s as task %s",
            project_id,
            result.id,
        )
    logger.info(
        "Enqueued %s project GeoJSON rebuilds; children run separately", len(tasks)
    )
    return {"enqueued": len(tasks), "tasks": tasks}
