#!/usr/bin/env python
# -*- coding: utf-8 -*-

import uuid
from typing import Self

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from speleodb.users.models import User
from speleodb.surveys.models import Project


class Permission(models.Model):
    class Meta:
        unique_together = ('user', 'project',)

    project = models.ForeignKey(
        Project,
        related_name="rel_permissions",
        on_delete=models.CASCADE,
    )

    user = models.ForeignKey(
        User,
        related_name="rel_permissions",
        on_delete=models.CASCADE
    )

    class Level(models.IntegerChoices):
        READ_ONLY = (0, "READ_ONLY")
        READ_AND_WRITE = (1, "READ_AND_WRITE")
        OWNER = (2, "SUDO")

    level = models.IntegerField(
        choices=Level.choices,
        default=Level.READ_ONLY,
        verbose_name="level"
    )

    @property
    def level_name(self) -> str:
        return self.Level(self.level).label

    def __str__(self):
        return f"{self.user} => {self.project} [{self.level_name}]"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    # @classmethod
    # def fetch_project_by_user(cls, user: User) -> Self:
    #     return cls
