#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import path

from speleodb.api.v1.views.user import ReleaseAllUserLocksView
from speleodb.api.v1.views.user import UserAuthTokenView
from speleodb.api.v1.views.user import UserInfo
from speleodb.api.v1.views.user import UserPasswordChangeView

urlpatterns: list[URLPattern] = [
    path("", UserInfo.as_view(), name="user_info"),
    path("auth-token/", UserAuthTokenView.as_view(), name="auth_token"),
    path("password/", UserPasswordChangeView.as_view(), name="update_user_password"),
    path(
        "release_all_locks/",
        ReleaseAllUserLocksView.as_view(),
        name="release_all_locks",
    ),
]
