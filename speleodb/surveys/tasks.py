# -*- coding: utf-8 -*-

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from celery import shared_task
from django.conf import settings
from django.core.management import call_command

from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import Project

if TYPE_CHECKING:
    from uuid import UUID


@shared_task()
def refresh_project_geojson(project_id: UUID) -> None:
    """Refresh the geojson for all projects."""
    project = Project.objects.get(id=project_id)

    with tempfile.TemporaryDirectory() as _temp_dir:
        temp_dir = Path(_temp_dir)

        # Clone the project in a temporary directory
        git_repo = GitlabManager.create_or_clone_project(project, temp_dir)
        if git_repo is None:
            raise RuntimeError(
                "Impossible to clone the project in a temporary directory."
            )

        _ = Path(git_repo.path).resolve()

    # for project in Project.objects.all():
    #     project.refresh_geojson()


@shared_task(
    soft_time_limit=settings.GEOJSON_REBUILD_SOFT_TIME_LIMIT,
    time_limit=settings.GEOJSON_REBUILD_HARD_TIME_LIMIT,
)
def refresh_all_projects_geojson() -> None:
    """Rebuild stored GeoJSON for every eligible project and historical commit."""
    call_command("build_project_geojsons", all_projects=True, force_recompute=True)
