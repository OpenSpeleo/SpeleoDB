# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING
from typing import Any

import gitlab
import gitlab.exceptions
from django.core.management.base import BaseCommand

from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.users.models import User

if TYPE_CHECKING:
    import argparse

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Wipe all local & gitlab repositories from a specified user."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--skip_user_confirmation",
            action="store_true",
            help=(
                "[DANGER] Actually proceed with the deletion. Execute first the script "
                "without this flag to verify everything is good."
            ),
        )

        parser.add_argument(
            "-u",
            "--user",
            dest="user_email",
            type=str,
            required=True,
            help="Deleting all local & gitlab projects of said user.",
        )

    def handle(
        self,
        *,
        skip_user_confirmation: bool = False,
        user_email: str,
        **kwargs: Any,
    ) -> None:
        user = User.objects.get(email=user_email)

        if not user.projects:
            logging.warning("The user currently does not have any project.")
            return

        gl_creds = GitlabCredentials.get()

        logger.warning("[IMPORTANT] This script is about to wipe all projects of:")
        logger.warning(f"\t- SpeleoDB User:   {user.email}")
        logger.warning(f"\t- Gitlab Group ID:   {gl_creds.group_id}")
        logger.warning(f"\t- Gitlab Group Name: {gl_creds.group_name}")
        logger.warning(f"\t- Gitlab Instance: {gl_creds.instance}")

        if not skip_user_confirmation:
            while True:
                confirmation = input(
                    "Is this the correct group? (Y/N, default N): "
                ).strip()

                if confirmation.upper() == "Y":
                    logger.info("Confirmed. Proceeding with the operation...")
                    break

                if confirmation.upper() == "N":
                    logger.info("Operation canceled.")
                    return

        self.stdout.write("")  # Visual Spacing

        GitlabManager._initialize()  # noqa: SLF001
        gl_creds = GitlabCredentials.get()
        gl_manager = GitlabManager._gl  # noqa: SLF001
        assert gl_manager is not None

        user_projects = user.projects

        for idx, project in enumerate(user_projects):
            print(  # noqa: T201
                f"[{idx + 1:03d}/{len(user_projects):03d}] "
                f"Deleting project: `{project.id}` ... ",
                end="",
            )

            try:
                gitproject = gl_manager.projects.get(
                    f"{gl_creds.group_name}/{project.id}"
                )
                gitproject.delete()  # Gitlab Delete
                project.delete()  # Django Delete
                print("Deleted!")  # noqa: T201
                time.sleep(5)
            except gitlab.exceptions.GitlabGetError:
                project.delete()  # Django Delete
                print("Skipped!")  # noqa: T201
