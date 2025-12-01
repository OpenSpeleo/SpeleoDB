# -*- coding: utf-8 -*-

from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models

from speleodb.surveys.models import Project


class ProjectCommit(models.Model):
    # Commit object ID (SHA)
    oid = models.CharField(
        max_length=40,
        primary_key=True,
        validators=[
            RegexValidator(regex=r"^[0-9a-f]{40}$", message="Enter a valid sha1 value")
        ],
        help_text="Specific commit SHA (40 hex chars).",
    )

    parents = models.JSONField(
        default=list,
        help_text="List of parent hexsha strings.",
        validators=[
            RegexValidator(
                regex=r"^([0-9a-f]{40},?)*$",
                message="Enter a valid list of sha1 values",
            )
        ],
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

    message = models.CharField(
        "commit message",
        blank=False,
        null=False,
        max_length=1024,
    )

    datetime = models.DateTimeField(null=False, blank=False)

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
        ordering = ("-datetime",)
        indexes = [
            models.Index(fields=["project"]),
            models.Index(fields=["project", "datetime"]),
        ]

    def __repr__(self) -> str:
        return f"{self} {self.author_name} <{self.author_email}>: {self.message}"

    def __str__(self) -> str:
        return f"[Commit {self.oid[:8]} - {self.datetime.isoformat()}]"

    @property
    def is_root(self) -> bool:
        """Return True if this is a root commit (no parents)."""
        return len(self.parents) == 0
