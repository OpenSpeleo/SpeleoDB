"""Verify GitLab identity and namespace, optionally testing repository writes."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from speleodb.git_engine.client import GitlabClient

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Command(BaseCommand):
    help = "Verify GitLab identity, namespace, and real project creation/deletion."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--read-only",
            action="store_true",
            help="Verify identity and namespace without creating a repository.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        client = GitlabClient(
            f"{settings.GITLAB_HTTP_PROTOCOL}://{settings.GITLAB_HOST_URL}",
            private_token=settings.GITLAB_TOKEN,
            keep_base_url=settings.GITLAB_HTTP_PROTOCOL == "http",
        )
        try:
            client.auth()
            if client.user is None:
                raise CommandError("GitLab authentication returned no user.")
            group = client.groups.get(settings.GITLAB_GROUP_ID)
            if group.full_path != settings.GITLAB_GROUP_NAME:
                raise CommandError(
                    "GITLAB_GROUP_ID and GITLAB_GROUP_NAME identify different groups."
                )
            self.stdout.write(
                f"GitLab host={settings.GITLAB_HOST_URL} "
                f"user={client.user.username} (id={client.user.id}) "
                f"group={group.full_path} (id={group.id})"
            )
            if options["read_only"]:
                self.stdout.write(
                    self.style.SUCCESS("GitLab authenticated read-only check passed.")
                )
                return
            project = client.projects.create(
                {
                    "name": f"ci-preflight-{uuid4().hex}",
                    "namespace_id": group.id,
                    "visibility": "private",
                }
            )
            project.delete()
            self.stdout.write(
                self.style.SUCCESS("GitLab authenticated write check passed.")
            )
        finally:
            client.session.close()
