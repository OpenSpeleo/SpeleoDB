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
from openspeleo_lib.errors import EmptySurveyError
from openspeleo_lib.geojson import NoKnownAnchorError
from openspeleo_lib.geojson import survey_to_geojson
from openspeleo_lib.interfaces import ArianeInterface

from speleodb.gis.models import ProjectGeoJSON
from speleodb.processors import ArianeTMLFileProcessor
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.utils.exceptions import GeoJSONGenerationError

if TYPE_CHECKING:
    import argparse

    from openspeleo_lib.models import Survey

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Download all the git projects to the local directory. Mostly useful for "
        "production servers to reduce user waiting time."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--force_recompute",
            action="store_true",
            help=(
                "Ignore that the GeoJSON file already exists, recompute and overwrite."
            ),
        )

    def handle(self, *, force_recompute: bool = False, **kwargs: Any) -> None:
        for project in Project.objects.filter(exclude_geojson=False).order_by(
            "-modified_date"
        ):
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
                        file = commit.tree / ArianeTMLFileProcessor.TARGET_SAVE_FILENAME  # pyright: ignore[reportOperatorIssue]

                    except KeyError:
                        # tree lookups raise KeyError when the path doesn't exist
                        logger.warning("No file to process found in this commit")
                        continue

                    try:
                        # Create a temporary file to store the TML content
                        # and then load it into the ArianeInterface
                        logger.info(f"Processing file: {file.path}")

                        # Use a temporary directory to avoid conflicts
                        with TemporaryDirectory() as tmp_dir:
                            tmp_file = Path(tmp_dir) / "object"
                            # / ArianeTMLFileProcessor.TARGET_SAVE_FILENAME

                            tmp_file.write_bytes(file.content.getvalue())
                            logger.info(f"Saved {file.path} to {tmp_file}")

                            try:
                                geojson_data = project.build_geojson(tmp_file)
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
                            f"Error processing file {file.path} in commit "
                            f"{commit.hexsha}"
                        )
                        continue

            except Exception:
                logger.exception(f"An error occured with project: {project.id}")

            finally:
                # Clean up the git repository working copy
                if (git_dir := project.git_repo_dir).exists():
                    shutil.rmtree(git_dir)
