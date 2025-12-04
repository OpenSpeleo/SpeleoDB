# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import TYPE_CHECKING

from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from speleodb.surveys.models import Project

if TYPE_CHECKING:
    from speleodb.git_engine.core import GitCommit


class ProjectCommit(models.Model):
    # Commit object ID (SHA)
    id = models.CharField(
        max_length=40,
        primary_key=True,
        validators=[
            RegexValidator(regex=r"^[0-9a-f]{40}$", message="Enter a valid sha1 value")
        ],
        help_text="Specific commit SHA (40 hex chars).",
    )

    project = models.ForeignKey(
        Project,
        related_name="commits",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
        editable=False,
    )

    author_name = models.CharField(
        "Name of User",
        blank=False,
        null=False,
        max_length=255,
    )

    author_email = models.EmailField(
        "email address",
        blank=False,
        null=False,
    )

    authored_date = models.DateTimeField(
        null=False,
        blank=False,
        help_text="Date and time when the commit was authored.",
    )

    message = models.CharField(
        "commit message",
        blank=False,
        null=False,
        max_length=1024,
    )

    parent_ids = models.JSONField(
        default=list,
        help_text="List of parent hexsha strings.",
        validators=[
            RegexValidator(
                regex=r"^([0-9a-f]{40},?)*$",
                message="Enter a valid list of sha1 values",
            )
        ],
    )

    #  git ls-tree -r HEAD | awk '{print "{\"mode\":\""$1"\", \"type\":\""$2"\", \"object\":\""$3"\", \"path\":\""$4"\"}"}' | jq -s .  # noqa: E501
    tree = models.JSONField(
        default=dict,
        blank=True,
        help_text="`git ls-tree -r` data.",
    )

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "Project Commit"
        verbose_name_plural = "Project Commits"
        ordering = ("-authored_date",)
        indexes = [
            models.Index(fields=["project"]),
            models.Index(fields=["project", "authored_date"]),
        ]

    def __repr__(self) -> str:
        return f"{self} {self.author_name} <{self.author_email}>: {self.message}"

    def __str__(self) -> str:
        return f"[Commit {self.id[:8]} - {self.authored_date.isoformat()}]"

    @property
    def is_root(self) -> bool:
        """Return True if this is a root commit (no parents)."""
        return len(self.parent_ids) == 0

    @classmethod
    def get_or_create_from_commit(
        cls, project: Project, commit: GitCommit
    ) -> ProjectCommit:
        with contextlib.suppress(cls.DoesNotExist):
            return ProjectCommit.objects.get(id=commit.hexsha)

        return ProjectCommit.objects.create(
            id=commit.hexsha,
            project=project,
            author_name=commit.author.name or "",
            author_email=commit.author.email or "",
            authored_date=datetime.fromtimestamp(
                commit.authored_date,
                tz=timezone.get_current_timezone(),
            ),
            message=(
                message
                if isinstance(message := commit.message, str)
                else message.decode("utf-8", errors="ignore")
            ),
            parent_ids=[parent.hexsha for parent in commit.parents],
            tree=commit.tree_to_json(),
        )
