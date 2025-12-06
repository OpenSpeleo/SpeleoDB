# -*- coding: utf-8 -*-

from __future__ import annotations

from django.db import models

from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import Project
from speleodb.surveys.models.permission_base import BasePermissionModel
from speleodb.users.models import SurveyTeam


class TeamProjectPermission(BasePermissionModel):
    target = models.ForeignKey(
        SurveyTeam,
        related_name="project_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    project = models.ForeignKey(
        Project,
        related_name="_team_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    class Meta:
        verbose_name = "Project - Team Permission"
        verbose_name_plural = "Project - Team Permissions"
        unique_together = ("target", "project")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(level__in=PermissionLevel.values_no_admin),
                name="%(app_label)s_%(class)s_level_is_valid",
            )
        ]
        indexes = [
            models.Index(fields=["target"]),
            models.Index(fields=["project"]),
            # models.Index(fields=["target", "project"]), # Present via unique constraint  # noqa: E501
        ]
