#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.users.api.v1.views import UserAuthTokenView
from speleodb.users.api.v1.views import UserInfo
from speleodb.users.api.v1.views import UserPasswordChangeView

app_name = "user_api"

urlpatterns = [
    path("user/auth-token/", UserAuthTokenView.as_view(), name="auth_token"),
    path("user/info/", UserInfo.as_view(), name="user_info"),
    path(
        "user/password/", UserPasswordChangeView.as_view(), name="update_user_password"
    ),
]
