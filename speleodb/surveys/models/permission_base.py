#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models

from speleodb.users.models import User


class BasePermissionModel(models.Model):
    # abstract parameter
    target = NotImplementedError()
    project = NotImplementedError()

    is_active = models.BooleanField(default=True)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    deactivated_by = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        blank=True,
        null=True,
        default=None,
    )

    class Level(models.IntegerChoices):
        READ_ONLY = (0, "READ_ONLY")
        READ_AND_WRITE = (1, "READ_AND_WRITE")
        # ADMIN = (2, "ADMIN")

    _level = models.IntegerField(
        choices=Level.choices, default=Level.READ_ONLY, verbose_name="level"
    )

    class Meta:
        abstract = True
        unique_together = ("target", "project")

    def __str__(self):
        return f"{self.target} => {self.project} [{self.level}]"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    @property
    def level_obj(self) -> str:
        return self.Level(self._level)

    @property
    def level(self) -> str:
        return self.level_obj.label

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
