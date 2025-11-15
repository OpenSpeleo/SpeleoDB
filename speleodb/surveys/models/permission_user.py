# -*- coding: utf-8 -*-

from __future__ import annotations

from django.db import models

from speleodb.surveys.models import Project
from speleodb.surveys.models.permission_base import BasePermissionModel
from speleodb.users.models import User


class UserProjectPermission(BasePermissionModel):
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
        verbose_name = "Project - User Permission"
        verbose_name_plural = "Project - User Permissions"
        unique_together = ("target", "project")
        indexes = [
            models.Index(fields=["target", "is_active"]),
            models.Index(fields=["project", "is_active"]),
            models.Index(fields=["target", "project", "is_active"]),
        ]
