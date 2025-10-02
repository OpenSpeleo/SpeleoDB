# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.views.team import TeamApiView
from speleodb.api.v1.views.team import TeamSpecificApiView
from speleodb.api.v1.views.team_membership import TeamMembershipApiView
from speleodb.api.v1.views.team_membership import TeamMembershipListApiView

team_url_patterns: list[URLPattern] = [
    path("", TeamSpecificApiView.as_view(), name="team-detail"),
    # Team Membership APIs
    path(
        "memberships/",
        TeamMembershipListApiView.as_view(),
        name="team-memberships",
    ),
    path(
        "memberships/detail/",
        TeamMembershipApiView.as_view(),
        name="team-memberships-detail",
    ),
]

urlpatterns: list[URLPattern | URLResolver] = [
    path("", TeamApiView.as_view(), name="teams"),
    path("<uuid:id>/", include(team_url_patterns)),
]
