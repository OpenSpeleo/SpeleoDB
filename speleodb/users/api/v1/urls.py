#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.users.api.v1.views.team import CreateTeamApiView
from speleodb.users.api.v1.views.team import TeamApiView
from speleodb.users.api.v1.views.team import TeamMembershipApiView
from speleodb.users.api.v1.views.user import UserAuthTokenView
from speleodb.users.api.v1.views.user import UserInfo
from speleodb.users.api.v1.views.user import UserPasswordChangeView

app_name = "user_api"

urlpatterns = [
    path("user/auth-token/", UserAuthTokenView.as_view(), name="auth_token"),
    path("user/info/", UserInfo.as_view(), name="user_info"),
    path(
        "user/password/", UserPasswordChangeView.as_view(), name="update_user_password"
    ),
    # ------------------------------ TEAM APIs ------------------------------ #
    path("team/", CreateTeamApiView.as_view(), name="create_team"),
    path("team/<int:id>/", TeamApiView.as_view(), name="one_team_apiview"),
    path(
        "team/<int:id>/membership/",
        TeamMembershipApiView.as_view(),
        name="team_membership",
    ),
]
