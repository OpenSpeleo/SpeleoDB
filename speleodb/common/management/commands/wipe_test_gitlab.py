# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import os
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import gitlab.exceptions
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from dotenv import load_dotenv

from speleodb.git_engine.client import GitlabClient
from speleodb.utils.confirmation import confirm_command

if TYPE_CHECKING:
    import argparse

logger = logging.getLogger(__name__)


def is_older_than(created_at: object, cutoff: datetime) -> bool:
    """Only a valid, timezone-aware creation date permits stale cleanup."""
    if not isinstance(created_at, str):
        return False
    try:
        created: datetime | None = parse_datetime(created_at)
    except ValueError:
        return False
    return created is not None and timezone.is_aware(created) and created < cutoff


class Command(BaseCommand):
    help = "Wipe all repositories from a specified GitLab group."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--older-than-hours",
            type=int,
            help="Only delete repositories created more than this many hours ago.",
        )
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
        older_than_hours: int | None = None,
        **kwargs: Any,
    ) -> None:
        if older_than_hours is not None and older_than_hours <= 0:
            raise CommandError("--older-than-hours must be positive.")
        cutoff: datetime | None = (
            timezone.now() - timedelta(hours=older_than_hours)
            if older_than_hours is not None
            else None
        )
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
            gl = GitlabClient(
                f"{settings.GITLAB_HTTP_PROTOCOL}://{os.environ['GITLAB_HOST_URL']}/",
                private_token=os.environ["GITLAB_TOKEN"],
                keep_base_url=settings.GITLAB_HTTP_PROTOCOL == "http",
            )
            group = gl.groups.get(os.environ["GITLAB_GROUP_ID"])

            logger.warning("[IMPORTANT] This script is about to wipe the Gitlab Group:")
            logger.warning(f"\t- ID:   {group.id}")
            logger.warning(f"\t- NAME: {group.full_name}")
            logger.warning(f"\t- URL : {group.web_url}")

            if not skip_user_confirmation:
                if not confirm_command("Is this the correct group? (Y/N, default N): "):
                    logger.info("Operation canceled.")
                    return
                logger.info("Confirmed. Proceeding with the operation...")

            self.stdout.write("")  # Visual Spacing
            projects = group.projects.list(all=True)

            if not projects:
                logger.info("No projects to delete.")
                return

            for project_id, project in enumerate(projects):
                if cutoff is not None and not is_older_than(
                    project.attributes.get("created_at"), cutoff
                ):
                    logger.info("Preserving recent project or unknown creation date.")
                    continue
                logger.info(
                    f"[{project_id + 1}/{len(projects)}] Processing project: "
                    f"`{project.name}` - {project.web_url}"
                )
                if accept_danger:  # Not a dummy run - Actually proceed
                    project_to_delete = gl.projects.get(project.id)
                    if project_to_delete.attributes.get("marked_for_deletion_at"):
                        logger.info("Already scheduled for deletion; skipping.")
                        continue
                    project_to_delete.delete()

        except gitlab.exceptions.RedirectError as e:
            raise CommandError(
                "GitLab redirected a write request. Use the final HTTPS URL and "
                "run this test cleanup with --settings=config.settings.test."
            ) from e

        except gitlab.exceptions.GitlabError as e:
            raise CommandError(
                f"GitLab cleanup failed: {type(e).__name__} (HTTP {e.response_code})."
            ) from e

        except Exception as e:
            raise CommandError(
                f"The GitLab cleanup could not finish ({type(e).__name__})."
            ) from e
