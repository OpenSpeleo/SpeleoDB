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
        indexes = [
            models.Index(fields=["target"]),
            models.Index(fields=["project"]),
            # models.Index(fields=["target", "project"]), # Present via unique constraint  # noqa: E501
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["target", "project"],
                name="%(app_label)s_%(class)s_user_project_unique",
            ),
        ]
