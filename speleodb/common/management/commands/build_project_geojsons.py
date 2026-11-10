# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING
from typing import Any

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from speleodb.common.enums import ProjectType
from speleodb.surveys.models import Project
from speleodb.utils.exceptions import reraise_task_timeout

if TYPE_CHECKING:
    import argparse

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

    def _process_project(self, project: Project, *, force_recompute: bool) -> None:
        summary = project.build_geojsons(force_recompute=force_recompute)
        logger.info("Project %s conversion: %s", project.pk, summary.as_dict())

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
            projects = Project.objects.filter(
                exclude_geojson=False,
                type__in=(
                    ProjectType.ARIANE,
                    ProjectType.COMPASS,
                    ProjectType.STALAGMIGHT,
                ),
            )
            if project_type is not None:
                projects = projects.filter(type=project_type)

            failures = 0
            for project in projects.order_by("-modified_date").iterator():
                try:
                    self._process_project(
                        project,
                        force_recompute=force_recompute,
                    )
                except Exception as exc:
                    reraise_task_timeout(exc)
                    failures += 1
                    logger.exception("An error occurred with project: %s", project.id)
            if failures:
                raise CommandError(
                    f"GeoJSON conversion failed for {failures} project(s)."
                )
            return

        if project_type is not None:
            raise CommandError("--project_type can only be used with --all.")

        if project_id is None:
            raise CommandError("--project must include a project UUID.")

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist as exc:
            raise CommandError(f"Project `{project_id}` does not exist.") from exc

        if project.exclude_geojson or not project.supports_geojson:
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
