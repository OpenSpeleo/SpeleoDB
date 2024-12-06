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

    is_active = models.BooleanField(default=True)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    deactivated_by = models.ForeignKey(
        User,
        related_name="rel_deactivated_permissions",
        on_delete=models.RESTRICT,
        blank=True,
        null=True,
        default=None,
    )

    class Level(models.IntegerChoices):
        READ_ONLY = (0, "READ_ONLY")
        READ_AND_WRITE = (1, "READ_AND_WRITE")
        ADMIN = (2, "ADMIN")

    _level = models.IntegerField(
        choices=Level.choices, default=Level.READ_ONLY, verbose_name="level"
    )

    class Meta:
        unique_together = ("user", "project")

    def __str__(self):
        return f"{self.user} => {self.project} [{self.level}]"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    @property
    def level(self) -> str:
        return self.Level(self._level).label

    @level.setter
    def level(self, value):
        self._level = value

    def deactivate(self, deactivated_by: User):
        self.is_active = False
        self.deactivated_by = deactivated_by
        self.save()

    def reactivate(self, level: Level):
        self.is_active = True
        self.deactivated_by = None
        self.level = level
        self.save()
