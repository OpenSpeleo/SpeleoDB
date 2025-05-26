#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import logging
import os
import time
from pathlib import Path
from typing import Any

import gitlab.exceptions
from django.core.management.base import BaseCommand
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Wipe all repositories from a specified GitLab group."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--accept_danger",
            action="store_true",
            help=(
                "[DANGER] Actually proceed with the deletion. Execute first the script "
                "without this flag to verify everything is good."
            ),
        )

        parser.add_argument(
            "--skip_user_confirmation",
            action="store_true",
            help=(
                "[DANGER] Actually proceed with the deletion. Execute first the script "
                "without this flag to verify everything is good."
            ),
        )

    def handle(
        self,
        *,
        skip_user_confirmation: bool = False,
        accept_danger: bool = False,
        **kwargs: Any,
    ) -> None:
        project_base_dir = Path(__file__).parents[4].resolve()
        if (env_file := project_base_dir / ".envs/test.env").exists():
            assert load_dotenv(env_file)
            logger.info(f"Loading Test Environment Variables File `{env_file}` ...")
        else:
            logger.warning(
                f"Test Environment Variables File `{env_file}` does not exist ..."
            )

        for env_var in [
            "GITLAB_GROUP_ID",
            "GITLAB_GROUP_NAME",
            "GITLAB_HOST_URL",
            "GITLAB_TOKEN",
        ]:
            assert env_var in os.environ
            value = os.environ[env_var]
            value = "#" * len(value) if env_var == "GITLAB_TOKEN" else value
            logger.info(f"[*] {env_var}: {value}")

        self.stdout.write("")  # Visual Spacing
        try:
            gl = gitlab.Gitlab(
                f"https://{os.environ['GITLAB_HOST_URL']}/",
                private_token=os.environ["GITLAB_TOKEN"],
            )
            group = gl.groups.get(os.environ["GITLAB_GROUP_ID"])

            logger.warning("[IMPORTANT] This script is about to wipe the Gitlab Group:")
            logger.warning(f"\t- ID:   {group.id}")
            logger.warning(f"\t- NAME: {group.full_name}")
            logger.warning(f"\t- URL : {group.web_url}")

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
            projects = group.projects.list(all=True)

            if not projects:
                logger.info("No projects to delete.")
                return

            for project_id, project in enumerate(projects):
                logger.info(
                    f"[{project_id + 1}/{len(projects)}] Deleting project: "
                    f"`{project.name}` - {project.web_url}"
                )
                if accept_danger:  # Not a dummy run - Actually proceed
                    project = gl.projects.get(project.id)  # noqa: PLW2901
                    project.delete()
                    time.sleep(5)  # Time Throttling Mitigation

        except gitlab.exceptions.GitlabGetError as e:
            self.stderr.write(f"Error fetching group: {e}")

        except Exception as e:  # noqa: BLE001
            self.stderr.write(f"Unexpected error: {e}")
