#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.api.v1.views.team import CreateTeamApiView
from speleodb.api.v1.views.team import TeamApiView
from speleodb.api.v1.views.team import TeamMembershipApiView

urlpatterns = [
    path("team/", CreateTeamApiView.as_view(), name="create_team"),
    path("team/<int:id>/", TeamApiView.as_view(), name="one_team_apiview"),
    path(
        "team/<int:id>/membership/",
        TeamMembershipApiView.as_view(),
        name="team_membership",
    ),
]
