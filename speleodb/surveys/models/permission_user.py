# -*- coding: utf-8 -*-

from __future__ import annotations

from django.db import models

from speleodb.surveys.models import Project
from speleodb.surveys.models.permission_base import BasePermissionModel
from speleodb.users.models import User


class UserPermission(BasePermissionModel):
    target = models.ForeignKey(
        User,
        related_name="rel_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    project = models.ForeignKey(
        Project,
        related_name="rel_user_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    class Meta:
        verbose_name = "User Permission"
        verbose_name_plural = "User Permissions"
        unique_together = ("target", "project")
