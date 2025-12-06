# -*- coding: utf-8 -*-

from __future__ import annotations

from django.db import models

from speleodb.surveys.models import Project
from speleodb.surveys.models.permission_base import BasePermissionModel
from speleodb.users.models import User


class UserProjectPermission(BasePermissionModel):
    target = models.ForeignKey(
        User,
        related_name="project_user_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    project = models.ForeignKey(
        Project,
        related_name="_user_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    class Meta:
        verbose_name = "Project - User Permission"
        verbose_name_plural = "Project - User Permissions"
        unique_together = ("target", "project")
        indexes = [
            models.Index(fields=["target"]),
            models.Index(fields=["project"]),
            # models.Index(fields=["target", "project"]), # Present via unique constraint  # noqa: E501
        ]
