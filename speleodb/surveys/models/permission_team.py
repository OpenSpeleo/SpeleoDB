# -*- coding: utf-8 -*-

from __future__ import annotations

from django.db import models

from speleodb.surveys.models import Project
from speleodb.surveys.models.permission_base import BasePermissionModel
from speleodb.surveys.models.permission_lvl import PermissionLevel
from speleodb.users.models import SurveyTeam


class TeamPermission(BasePermissionModel):
    target = models.ForeignKey(
        SurveyTeam,
        related_name="rel_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    project = models.ForeignKey(
        Project,
        related_name="rel_team_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    class Meta:
        verbose_name = "Team Permission"
        verbose_name_plural = "Team Permissions"
        unique_together = ("target", "project")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(level__in=PermissionLevel.values_no_admin),
                name="%(app_label)s_%(class)s_level_is_valid",
            )
        ]
