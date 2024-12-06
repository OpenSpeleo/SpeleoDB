#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models

from speleodb.surveys.model_files.permission_base import BasePermissionModel
from speleodb.surveys.models import Project
from speleodb.users.models import SurveyTeam


class TeamPermission(BasePermissionModel):
    target = models.ForeignKey(
        SurveyTeam, related_name="rel_permissions", on_delete=models.CASCADE
    )

    project = models.ForeignKey(
        Project,
        related_name="rel_team_permissions",
        on_delete=models.CASCADE,
    )

    class Meta(BasePermissionModel.Meta):
        verbose_name = "Team Permission"
        verbose_name_plural = "Team Permissions"
