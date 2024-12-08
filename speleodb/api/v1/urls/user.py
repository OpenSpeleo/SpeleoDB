#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.api.v1.views.user import UserAuthTokenView
from speleodb.api.v1.views.user import UserInfo
from speleodb.api.v1.views.user import UserPasswordChangeView

urlpatterns = [
    path("user/auth-token/", UserAuthTokenView.as_view(), name="auth_token"),
    path("user/info/", UserInfo.as_view(), name="user_info"),
    path(
        "user/password/", UserPasswordChangeView.as_view(), name="update_user_password"
    ),
]
