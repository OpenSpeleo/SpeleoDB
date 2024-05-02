#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models

from speleodb.surveys.models import Project
from speleodb.users.models import User


class Permission(models.Model):
    project = models.ForeignKey(
        Project,
        related_name="rel_permissions",
        on_delete=models.CASCADE,
    )

    user = models.ForeignKey(
        User, related_name="rel_permissions", on_delete=models.CASCADE
    )

    class Level(models.IntegerChoices):
        READ_ONLY = (0, "READ_ONLY")
        READ_AND_WRITE = (1, "READ_AND_WRITE")
        OWNER = (2, "SUDO")

    level = models.IntegerField(
        choices=Level.choices, default=Level.READ_ONLY, verbose_name="level"
    )

    class Meta:
        unique_together = ("user", "project")

    def __str__(self):
        return f"{self.user} => {self.project} [{self.level_name}]"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    @property
    def level_name(self) -> str:
        return self.Level(self.level).label
