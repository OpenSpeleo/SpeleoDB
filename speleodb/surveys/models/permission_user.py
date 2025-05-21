#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models

from speleodb.surveys.models import Project
from speleodb.surveys.models.permission_base import BasePermissionModel
from speleodb.users.models import User
from speleodb.utils.django_base_models import BaseIntegerChoices


class UserPermission(BasePermissionModel):
    target = models.ForeignKey(
        User, related_name="rel_permissions", on_delete=models.CASCADE
    )

    project = models.ForeignKey(
        Project,
        related_name="rel_user_permissions",
        on_delete=models.CASCADE,
    )

    class Level(BaseIntegerChoices):
        READ_ONLY = (
            BasePermissionModel.Level.READ_ONLY,
            BasePermissionModel.Level.READ_ONLY.label,
        )
        READ_AND_WRITE = (
            BasePermissionModel.Level.READ_AND_WRITE,
            BasePermissionModel.Level.READ_AND_WRITE.label,
        )
        ADMIN = (2, "ADMIN")

    _level = models.IntegerField(
        choices=Level.choices, default=Level.READ_ONLY, verbose_name="level"
    )

    class Meta(BasePermissionModel.Meta):
        verbose_name = "User Permission"
        verbose_name_plural = "User Permissions"
