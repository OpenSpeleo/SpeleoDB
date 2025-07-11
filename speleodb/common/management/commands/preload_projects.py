# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand

from speleodb.surveys.models import Project

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Download all the git projects to the local directory. Mostly useful for "
        "production servers to reduce user waiting time."
    )

    def handle(self, *args: Any, **kwargs: Any) -> None:
        for project in Project.objects.all():
            logger.info(f"Processing Project: {project.id}")
            try:
                _ = project.git_repo  # load the git project
            except Exception:
                logger.exception(f"An error occured with project: {project.id}")
