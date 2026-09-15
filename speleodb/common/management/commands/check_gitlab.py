"""Fail CI before the suite when its actual GitLab credentials cannot write."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from speleodb.git_engine.client import GitlabClient


class Command(BaseCommand):
    help = "Verify GitLab identity, namespace, and real project creation/deletion."

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
