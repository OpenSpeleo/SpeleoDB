#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.db import models

from speleodb.surveys.models import Project
from speleodb.users.models import SurveyTeam
from speleodb.users.models import User
from speleodb.utils.django_base_models import BaseIntegerChoices


class BasePermissionModel(models.Model):
    # abstract parameter
    target: models.ForeignKey[User | SurveyTeam]
    project: models.ForeignKey[Project]

    is_active = models.BooleanField(default=True)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    deactivated_by = models.ForeignKey[User | None](
        User,
        on_delete=models.RESTRICT,
        null=True,
        default=None,
    )

    class Level(BaseIntegerChoices):
        READ_ONLY = (0, "READ_ONLY")
        READ_AND_WRITE = (1, "READ_AND_WRITE")
        # ADMIN = (2, "ADMIN")

    _level = models.IntegerField(
        choices=Level.choices, default=Level.READ_ONLY, verbose_name="level"
    )

    class Meta:
        abstract = True
        unique_together = ("target", "project")

    def __str__(self) -> str:
        return f"{self.target} => {self.project} [{self.level}]"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    @property
    def level_obj(self) -> Level:
        return self.Level(int(self._level))

    @level_obj.setter
    def level_obj(self, value: Level) -> None:
        self._level = value

    @property
    def level(self) -> str:
        return self.level_obj.label

    @level.setter
    def level(self, value: str) -> None:
        self._level = self.Level(value)

    def deactivate(self, deactivated_by: User) -> None:
        self.is_active = False
        self.deactivated_by = deactivated_by
        self.save()

    def reactivate(self, level: Level) -> None:
        self.is_active = True
        self.deactivated_by = None
        self.level_obj = level
        self.save()
