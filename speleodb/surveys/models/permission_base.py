#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models

from speleodb.surveys.models.permission_lvl import PermissionLevel
from speleodb.users.models import User


class BasePermissionModel(models.Model):
    # level: models.IntegerField  # type: ignore[arg-type]

    # level = choicefield.ChoiceField

    level = models.IntegerField(
        choices=PermissionLevel.choices, default=PermissionLevel.READ_ONLY
    )

    is_active = models.BooleanField(default=True)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    deactivated_by = models.ForeignKey(
        User, on_delete=models.RESTRICT, null=True, default=None, blank=True
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.target} => {self.project} [{self.level}]"  # type: ignore[attr-defined]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def deactivate(self, deactivated_by: User) -> None:
        self.is_active = False
        self.deactivated_by = deactivated_by
        self.save()

    def reactivate(self, level: PermissionLevel) -> None:
        self.is_active = True
        self.deactivated_by = None
        self.level = level
        self.save()
