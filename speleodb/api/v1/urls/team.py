#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.api.v1.views.team import CreateTeamApiView
from speleodb.api.v1.views.team import ListUserTeams
from speleodb.api.v1.views.team import TeamApiView
from speleodb.api.v1.views.team_membership import TeamMembershipApiView
from speleodb.api.v1.views.team_membership import TeamMembershipListApiView

urlpatterns = [
    path("team/", CreateTeamApiView.as_view(), name="create_team"),
    path("team/<int:id>/", TeamApiView.as_view(), name="one_team_apiview"),
    path(
        "team/<int:id>/membership/",
        TeamMembershipApiView.as_view(),
        name="team_membership",
    ),
    path(
        "team/<int:id>/memberships/",
        TeamMembershipListApiView.as_view(),
        name="team_list_membership",
    ),
    path("teams/", ListUserTeams.as_view(), name="list_user_teams"),
]
