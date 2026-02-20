# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import Any

import orjson
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand

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
    help = (
        "Download all the git projects to the local directory. Mostly useful for "
        "production servers to reduce user waiting time."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--project_type",
            default=None,
            choices=[*ProjectType.values, None],
            help=(
                "Ignore that the GeoJSON file already exists, recompute and overwrite."
            ),
        )

        parser.add_argument(
            "--force_recompute",
            action="store_true",
            help=(
                "Ignore that the GeoJSON file already exists, recompute and overwrite."
            ),
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

    def handle(
        self,
        *,
        project_type: ProjectType | None,
        force_recompute: bool = False,
        **kwargs: Any,
    ) -> None:
        qs = Project.objects.filter(exclude_geojson=False)

        if project_type is not None:
            qs = qs.filter(type=project_type)

        for project in qs.order_by("-modified_date"):
            logger.info("")
            logger.info("-" * 60)
            logger.info(f"Processing Project: {project.id} ~ {project.name}")

            try:
                git_repo = project.git_repo  # load the git project

                for commit in git_repo.commits:
                    with contextlib.suppress(ProjectGeoJSON.DoesNotExist):
                        obj = ProjectGeoJSON.objects.get(
                            # Globally unique. Does not need to specify the project
                            commit__id=commit.hexsha,
                        )

                        if not force_recompute:
                            logger.info(
                                f"GeoJSON for commit {commit.hexsha} already exists. "
                                "Skipping ..."
                            )
                            continue

                        # Force remove the GeoJSON file
                        obj.delete()

                    logger.info(
                        f"Processing commit: {commit.hexsha} - {commit.date_dt}"
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
                                "test.geojson",  # filename
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
                            f"Error processing project source in commit {commit.hexsha}"
                        )
                        continue

            except Exception:
                logger.exception(f"An error occured with project: {project.id}")

            finally:
                # Clean up the git repository working copy
                if (git_dir := project.git_repo_dir).exists():
                    shutil.rmtree(git_dir)
