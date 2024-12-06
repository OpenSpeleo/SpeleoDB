#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models

from speleodb.surveys.model_files.permission_base import BasePermissionModel
from speleodb.surveys.models import Project
from speleodb.users.models import User


class UserPermission(BasePermissionModel):
    target = models.ForeignKey(
        User, related_name="rel_permissions", on_delete=models.CASCADE
    )

    project = models.ForeignKey(
        Project,
        related_name="rel_user_permissions",
        on_delete=models.CASCADE,
    )

    class Level(models.IntegerChoices):
        READ_ONLY = BasePermissionModel.Level.READ_ONLY
        READ_AND_WRITE = BasePermissionModel.Level.READ_AND_WRITE
        ADMIN = (2, "ADMIN")

    _level = models.IntegerField(
        choices=Level.choices, default=Level.READ_ONLY, verbose_name="level"
    )

    class Meta(BasePermissionModel.Meta):
        verbose_name = "User Permission"
        verbose_name_plural = "User Permissions"
