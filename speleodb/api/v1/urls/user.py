# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import path

from speleodb.api.v1.views.user import ReleaseAllUserLocksView
from speleodb.api.v1.views.user import UserAuthTokenView
from speleodb.api.v1.views.user import UserAutocompleteView
from speleodb.api.v1.views.user import UserInfo
from speleodb.api.v1.views.user import UserPasswordChangeView

urlpatterns: list[URLPattern] = [
    path("", UserInfo.as_view(), name="user-detail"),
    path("auth-token/", UserAuthTokenView.as_view(), name="user-auth-token"),
    path("password/", UserPasswordChangeView.as_view(), name="user-password-update"),
    path(
        "release_all_locks/",
        ReleaseAllUserLocksView.as_view(),
        name="release-all-locks",
    ),
    path("autocomplete/", UserAutocompleteView.as_view(), name="user-autocomplete"),
]
