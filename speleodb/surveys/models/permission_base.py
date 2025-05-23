#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models

from speleodb.surveys.models.permission_lvl import PermissionLevel
from speleodb.users.models import User


class BasePermissionModel(models.Model):
    _level: models.IntegerField

    is_active = models.BooleanField(default=True)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    deactivated_by = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        null=True,
        default=None,
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.target} => {self.project} [{self.level}]"  # type: ignore[attr-defined]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    @property
    def level_obj(self) -> PermissionLevel:
        return PermissionLevel(self._level)

    @level_obj.setter
    def level_obj(self, value: PermissionLevel) -> None:
        self._level = value

    @property
    def level(self) -> str:
        return self.level_obj.label

    @level.setter
    def level(self, value: str) -> None:
        self._level = PermissionLevel(value)

    def deactivate(self, deactivated_by: User) -> None:
        self.is_active = False
        self.deactivated_by = deactivated_by
        self.save()

    def reactivate(self, level: PermissionLevel) -> None:
        self.is_active = True
        self.deactivated_by = None
        self.level_obj = level
        self.save()
