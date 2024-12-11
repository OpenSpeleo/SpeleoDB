#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.api.v1.views.team_permission import ProjectTeamPermissionListView
from speleodb.api.v1.views.team_permission import ProjectTeamPermissionView
from speleodb.api.v1.views.user_permission import ProjectUserPermissionListView
from speleodb.api.v1.views.user_permission import ProjectUserPermissionView

urlpatterns = [
    # --------- USER PERMISSIONS --------- #
    path(
        "project/<uuid:id>/permissions/user/",
        ProjectUserPermissionListView.as_view(),
        name="list_project_user_permissions",
    ),
    path(
        "project/<uuid:id>/permission/user/",
        ProjectUserPermissionView.as_view(),
        name="project_user_permission",
    ),
    # --------- TEAM PERMISSIONS --------- #
    path(
        "project/<uuid:id>/permissions/team/",
        ProjectTeamPermissionListView.as_view(),
        name="list_project_team_permissions",
    ),
    path(
        "project/<uuid:id>/permission/team/",
        ProjectTeamPermissionView.as_view(),
        name="project_team_permission",
    ),
]
