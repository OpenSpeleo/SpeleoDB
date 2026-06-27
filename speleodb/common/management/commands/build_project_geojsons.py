# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
import shutil
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import Any

import orjson
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from speleodb.common.enums import ProjectType
from speleodb.gis.models import ProjectGeoJSON
from speleodb.git_engine.core import GitFile
from speleodb.processors import ArianeTMLFileProcessor
from speleodb.processors._impl.compass_toml import CompassTOML
from speleodb.processors._impl.compass_toml import get_compass_mak_filepath
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.utils.exceptions import GeoJSONGenerationError

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
            "--fresh",
            action="store_true",
            help=(
                "Delete the selected project's local copy before cloning it from "
                "GitLab. Only valid with --project."
            ),
        )
        parser.add_argument(
            "--project_type",
            default=None,
            choices=ProjectType.values,
            help="Limit --all processing to projects of this type.",
        )
        parser.add_argument(
            "--force_recompute",
            action="store_true",
            help="Recompute and replace GeoJSON files that already exist.",
        )

    def _materialize_ariane_source(
        self, commit: GitCommit, tmp_dirpath: Path
    ) -> Path | None:
        try:
            file = commit.tree / ArianeTMLFileProcessor.TARGET_SAVE_FILENAME
        except KeyError:
            return None

        tmp_file = tmp_dirpath / ArianeTMLFileProcessor.TARGET_SAVE_FILENAME
        tmp_file.write_bytes(file.content.getvalue())
        return tmp_file

    def _materialize_compass_source(
        self, commit: GitCommit, tmp_dirpath: Path
    ) -> Path | None:
        files_by_path: dict[str, GitFile] = {
            str(item.path): item
            for item in commit.tree.traverse()
            if isinstance(item, GitFile)
        }

        compass_toml_file = files_by_path.get(CompassTOML.__FILENAME__)
        if compass_toml_file is None:
            return None

        cfg = CompassTOML.from_toml(compass_toml_file.content)

        for rel_path in cfg.files:
            git_file = files_by_path.get(rel_path)
            if git_file is None:
                logger.warning(
                    "Missing Compass file `%s` in commit `%s`",
                    rel_path,
                    commit.hexsha,
                )
                return None

            target_path = tmp_dirpath / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(git_file.content.getvalue())

        return get_compass_mak_filepath(tmp_dirpath)

    def _materialize_geojson_source(
        self, project: Project, commit: GitCommit, tmp_dirpath: Path
    ) -> Path | None:
        match project.type:
            case ProjectType.ARIANE:
                return self._materialize_ariane_source(commit, tmp_dirpath)
            case ProjectType.COMPASS:
                return self._materialize_compass_source(commit, tmp_dirpath)
            case _:
                return None

    @staticmethod
    def _remove_local_copy(project: Project) -> None:
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(project.git_repo_dir)

    def _process_project(
        self,
        project: Project,
        *,
        force_recompute: bool,
        fresh: bool = False,
    ) -> None:
        logger.info("")
        logger.info("-" * 60)
        logger.info("Processing Project: %s ~ %s", project.id, project.name)

        try:
            if fresh:
                self._remove_local_copy(project)

            git_repo = project.git_repo

            for commit in git_repo.commits:
                with contextlib.suppress(ProjectGeoJSON.DoesNotExist):
                    obj = ProjectGeoJSON.objects.get(
                        # Globally unique. Does not need to specify the project.
                        commit__id=commit.hexsha,
                    )

                    if not force_recompute:
                        logger.info(
                            "GeoJSON for commit %s already exists. Skipping ...",
                            commit.hexsha,
                        )
                        continue

                    obj.delete()

                logger.info(
                    "Processing commit: %s - %s", commit.hexsha, commit.date_dt
                )

                try:
                    with TemporaryDirectory() as tmp_dir:
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
                        except GeoJSONGenerationError:
                            continue

                        geojson_f = SimpleUploadedFile(
                            "test.geojson",
                            orjson.dumps(geojson_data),
                            content_type="application/geo+json",
                        )

                        commit_obj = ProjectCommit.get_or_create_from_commit(
                            project=project,
                            commit=commit,
                        )

                        ProjectGeoJSON.objects.create(
                            project=project,
                            commit=commit_obj,
                            file=geojson_f,
                        )

                except Exception:
                    logger.exception(
                        "Error processing project source in commit %s", commit.hexsha
                    )
                    continue
        finally:
            self._remove_local_copy(project)

    def handle(
        self,
        *,
        all_projects: bool = False,
        project_id: uuid.UUID | None = None,
        fresh: bool = False,
        project_type: str | None = None,
        force_recompute: bool = False,
        **kwargs: Any,
    ) -> None:
        if all_projects == (project_id is not None):
            raise CommandError("Exactly one of --all or --project must be provided.")

        if all_projects:
            if fresh:
                raise CommandError("--fresh can only be used with --project.")

            projects = Project.objects.filter(exclude_geojson=False)
            if project_type is not None:
                projects = projects.filter(type=project_type)

            for project in projects.order_by("-modified_date"):
                try:
                    self._process_project(
                        project,
                        force_recompute=force_recompute,
                    )
                except Exception:
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
                fresh=fresh,
            )
        except Exception as exc:
            logger.exception("An error occurred with project: %s", project.id)
            raise CommandError(
                f"Unable to build GeoJSON files for project `{project.id}`."
            ) from exc
