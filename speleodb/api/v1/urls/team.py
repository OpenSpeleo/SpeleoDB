#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.views.team import TeamApiView
from speleodb.api.v1.views.team import TeamSpecificApiView
from speleodb.api.v1.views.team_membership import TeamMembershipApiView
from speleodb.api.v1.views.team_membership import TeamMembershipListApiView

team_url_patterns: list[URLPattern] = [
    path("", TeamSpecificApiView.as_view(), name="one_team_apiview"),
    # Team Membership APIs
    path(
        "membership/",
        TeamMembershipApiView.as_view(),
        name="team_membership",
    ),
    path(
        "memberships/",
        TeamMembershipListApiView.as_view(),
        name="team_list_membership",
    ),
]

urlpatterns: list[URLPattern | URLResolver] = [
    path("", TeamApiView.as_view(), name="team_api"),
    path("<int:id>/", include(team_url_patterns)),
]
