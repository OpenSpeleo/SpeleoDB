# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import Any

import orjson
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from openspeleo_lib.geojson import NoKnownAnchorError
from openspeleo_lib.geojson import survey_to_geojson
from openspeleo_lib.interfaces import ArianeInterface

from speleodb.surveys.models import GeoJSON
from speleodb.surveys.models import Project

if TYPE_CHECKING:
    from openspeleo_lib.models import Survey

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Download all the git projects to the local directory. Mostly useful for "
        "production servers to reduce user waiting time."
    )

    def handle(self, *args: Any, **kwargs: Any) -> None:
        for project in Project.objects.filter(exclude_geojson=False):
            logger.info("")
            logger.info("-" * 60)
            logger.info(f"Processing Project: {project.id}")
            try:
                git_repo = project.git_repo  # load the git project

                for commit in git_repo.commits:
                    # Download all the geojson files for each commit
                    if GeoJSON.objects.filter(
                        project=project, commit_sha=commit.hexsha
                    ).exists():
                        logger.info(
                            f"GeoJSON for commit {commit.hexsha} already exists for "
                            f"project {project.id}. Skipping ..."
                        )
                        continue

                    logger.info(
                        f"Processing commit: {commit.hexsha} - {commit.date_dt}"
                    )

                    for file in commit.files:
                        try:
                            if Path(file.path).suffix != ".tml":
                                continue

                            # Create a temporary file to store the TML content
                            # and then load it into the ArianeInterface
                            logger.info(f"Processing file: {file.path}")

                            # Use a temporary directory to avoid conflicts
                            with TemporaryDirectory() as tmp_dir:
                                tmp_file = Path(tmp_dir) / "project.tml"
                                tmp_file.write_bytes(file.content.getvalue())
                                logger.info(f"Saved {file.path} to {tmp_file}")

                                with contextlib.suppress(NoKnownAnchorError):
                                    survey: Survey = ArianeInterface.from_file(tmp_file)
                                    geojson_data = survey_to_geojson(survey)

                                    geojson_f = SimpleUploadedFile(
                                        "test.geojson",  # filename
                                        orjson.dumps(geojson_data),
                                        content_type="application/geo+json",
                                    )

                                    GeoJSON.objects.create(
                                        project=project,
                                        commit_sha=commit.hexsha,
                                        commit_date=commit.date_dt,
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
