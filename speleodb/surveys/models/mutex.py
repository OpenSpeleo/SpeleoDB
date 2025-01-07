#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models
from django.db import transaction

from speleodb.surveys.models import Project
from speleodb.users.models import User


class Mutex(models.Model):
    project = models.ForeignKey(
        Project,
        related_name="rel_mutexes",
        on_delete=models.CASCADE,
    )

    user = models.ForeignKey(
        User, related_name="rel_mutexes", on_delete=models.RESTRICT
    )

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    closing_user = models.ForeignKey(
        User,
        related_name="rel_closing_mutexes",
        on_delete=models.RESTRICT,
        blank=True,
        null=True,
        default=None,
    )
    closing_comment = models.TextField(blank=True, default="")

    class Meta:
        verbose_name_plural = "mutexes"

    def __str__(self) -> str:
        return f"{self.user} => {self.project} @ {self.creation_date}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    @transaction.atomic
    def release_mutex(self, user: User, comment: str) -> None:
        mutexed_project: Project = self.project
        mutexed_project.active_mutex = None
        mutexed_project.save()

        self.closing_user = user
        self.closing_comment = comment
        self.save()

    @property
    def is_active(self) -> bool:
        return self.closing_user is None
