"""Generate a saved revision once; failures are rerun explicitly by operators."""

from __future__ import annotations

from typing import Any

from celery import shared_task
from celery.exceptions import Ignore
from django.conf import settings

from speleodb.background_jobs.operation_execution import operation_execution
from speleodb.surveys.models import ProjectCommit


@shared_task(
    bind=True,
    name="speleodb.gis.tasks.generate_project_geojson",
    track_started=False,
    acks_late=False,
    reject_on_worker_lost=False,
    max_retries=0,
    soft_time_limit=settings.GEOJSON_GENERATION_SOFT_TIME_LIMIT,
    time_limit=settings.GEOJSON_GENERATION_HARD_TIME_LIMIT,
)
def generate_project_geojson(self: Any, commit_id: str) -> dict[str, Any]:
    with operation_execution(self.request.id) as execution:
        if execution is None:
            raise Ignore
        execution.progress("convert")
        commit = ProjectCommit.objects.select_related("project").get(pk=commit_id)
        summary = commit.project.build_geojsons(revision=commit_id)
        data = summary.as_dict()
        execution.complete(data)
        return data
