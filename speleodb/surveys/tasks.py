# -*- coding: utf-8 -*-

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from celery import shared_task

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


@shared_task()
def refresh_all_projects_geojson() -> None:
    """Refresh the geojson for all projects."""
    for project in Project.objects.all():
        _ = refresh_project_geojson.delay(project.id)
