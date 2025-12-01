# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import shutil
from typing import Any

from django.core.management.base import BaseCommand

from speleodb.surveys.models import Project

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Preload all the `ProjectCommit` in database. Mostly useful for cold start or "
        "warm-up the git history cache."
    )

    def handle(self, *args: Any, **kwargs: Any) -> None:
        for project in Project.objects.filter(exclude_geojson=False).order_by(
            "-modified_date"
        ):
            logger.info("")
            logger.info("-" * 60)
            logger.info(f"Processing Project: {project.id} ~ {project.name}")

            try:
                git_repo = project.git_repo
                git_repo.checkout_default_branch_and_pull()
                project.construct_git_history_from_project(git_repo)

            except Exception:
                logger.exception(f"An error occured with project: {project.id}")

            finally:
                # Clean up the git repository working copy
                if (git_dir := project.git_repo_dir).exists():
                    shutil.rmtree(git_dir)
