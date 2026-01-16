# -*- coding: utf-8 -*-

from __future__ import annotations

from django.db import models
from django.db.models import indexes

from speleodb.surveys.models import Project
from speleodb.users.models import User


class ProjectMutex(models.Model):
    project = models.ForeignKey(
        Project,
        related_name="mutexes",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    user = models.ForeignKey(
        User,
        related_name="mutexes",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
    )

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    closing_user = models.EmailField(
        blank=True,
        help_text="User who released the mutex.",
    )

    closing_comment = models.TextField(blank=True, default="")

    class Meta:
        verbose_name_plural = "mutexes"
        indexes = [
            indexes.Index(fields=["is_active"]),
            indexes.Index(fields=["project"]),
            indexes.Index(fields=["user"]),
            indexes.Index(fields=["project", "user"]),
            indexes.Index(fields=["project", "user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"[ProjectMutex] {self.user} => {self.project} @ {self.creation_date}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def release_mutex(self, user: User, comment: str) -> None:
        self.is_active = False
        self.closing_user = user.email
        self.closing_comment = comment
        self.save()
