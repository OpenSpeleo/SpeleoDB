# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import Any

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from speleodb.background_jobs.archive_sources import mirror_project
from speleodb.background_jobs.archive_sources import project_git_source
from speleodb.common.enums import ProjectType
from speleodb.gis.geojson_sources import materialize_geojson_source
from speleodb.gis.geojson_workspaces import geojson_workspace
from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.project_geojson_services import replace_project_geojson
from speleodb.git_engine.core import GitRepo
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.utils.exceptions import GeoJSONGenerationError
from speleodb.utils.exceptions import reraise_task_timeout

if TYPE_CHECKING:
    import argparse

    from speleodb.git_engine.core import GitCommit

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Build stored GeoJSON files for all eligible projects or one project."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        selection_group = parser.add_mutually_exclusive_group(required=True)
        selection_group.add_argument(
            "--all",
            action="store_true",
            dest="all_projects",
            help="Build GeoJSON files for all projects that allow GeoJSON generation.",
        )
        selection_group.add_argument(
            "--project",
            type=uuid.UUID,
            dest="project_id",
            help="Build GeoJSON files for the project with this UUID.",
        )

        parser.add_argument(
            "--project_type",
            default=None,
            choices=ProjectType.values,
            help="Limit --all processing to projects of this type.",
        )
        parser.add_argument(
            "--force_recompute",
            "--force-recompute",
            action="store_true",
            help="Recompute and replace GeoJSON files that already exist.",
        )

    def _materialize_geojson_source(
        self, project: Project, commit: GitCommit, tmp_dirpath: Path
    ) -> Path | None:
        return materialize_geojson_source(project, commit, tmp_dirpath)

    def _process_project(
        self,
        project: Project,
        *,
        force_recompute: bool,
    ) -> None:
        logger.info("")
        logger.info("-" * 60)
        logger.info("Processing Project: %s ~ %s", project.id, project.name)

        with geojson_workspace(prefix="rebuild-") as directory:
            repository = directory / "repository"
            mirrored = mirror_project(
                project_git_source(
                    project.pk, has_recorded_history=project.commits.exists()
                ),
                repository,
                heartbeat=lambda: None,
            )
            if mirrored.state != "mirrored":
                logger.info("No Git history to rebuild for project %s", project.id)
                return
            with contextlib.closing(GitRepo(repository)) as git_repo:
                self._process_history(
                    project,
                    git_repo,
                    directory,
                    force_recompute=force_recompute,
                )

    def _process_history(
        self,
        project: Project,
        git_repo: GitRepo,
        directory: Path,
        *,
        force_recompute: bool,
    ) -> None:
        for commit in git_repo.commits:
            with contextlib.suppress(ProjectGeoJSON.DoesNotExist):
                ProjectGeoJSON.objects.get(
                    # Globally unique. Does not need to specify the project.
                    commit__id=commit.hexsha,
                )

                if not force_recompute:
                    logger.info(
                        "GeoJSON for commit %s already exists. Skipping ...",
                        commit.hexsha,
                    )
                    continue

            logger.info("Processing commit: %s - %s", commit.hexsha, commit.date_dt)

            try:
                with TemporaryDirectory(prefix="sources-", dir=directory) as tmp_dir:
                    source_path = self._materialize_geojson_source(
                        project=project,
                        commit=commit,
                        tmp_dirpath=Path(tmp_dir),
                    )

                    if source_path is None:
                        logger.warning(
                            "No `%s` source file found in commit `%s`",
                            project.type,
                            commit.hexsha,
                        )
                        continue

                    try:
                        geojson_data = project.build_geojson(source_path)
                    except GeoJSONGenerationError as exc:
                        reraise_task_timeout(exc)
                        continue

                    commit_obj = ProjectCommit.get_or_create_from_commit(
                        project=project,
                        commit=commit,
                    )

                    replace_project_geojson(
                        project,
                        commit_obj,
                        geojson_data,
                        replace_existing=force_recompute,
                    )

            except Exception as exc:
                reraise_task_timeout(exc)
                logger.exception(
                    "Error processing project source in commit %s", commit.hexsha
                )
                continue

    def handle(
        self,
        *,
        all_projects: bool = False,
        project_id: uuid.UUID | None = None,
        project_type: str | None = None,
        force_recompute: bool = False,
        **kwargs: Any,
    ) -> None:
        if all_projects == (project_id is not None):
            raise CommandError("Exactly one of --all or --project must be provided.")

        if all_projects:
            projects = Project.objects.filter(exclude_geojson=False)
            if project_type is not None:
                projects = projects.filter(type=project_type)

            for project in projects.order_by("-modified_date").iterator():
                try:
                    self._process_project(
                        project,
                        force_recompute=force_recompute,
                    )
                except Exception as exc:
                    reraise_task_timeout(exc)
                    logger.exception("An error occurred with project: %s", project.id)
            return

        if project_type is not None:
            raise CommandError("--project_type can only be used with --all.")

        if project_id is None:
            raise CommandError("--project must include a project UUID.")

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist as exc:
            raise CommandError(f"Project `{project_id}` does not exist.") from exc

        if project.exclude_geojson:
            raise CommandError(
                f"Project `{project.id}` is excluded from GeoJSON generation."
            )

        try:
            self._process_project(
                project,
                force_recompute=force_recompute,
            )
        except Exception as exc:
            reraise_task_timeout(exc)
            logger.exception("An error occurred with project: %s", project.id)
            raise CommandError(
                f"Unable to build GeoJSON files for project `{project.id}`."
            ) from exc
