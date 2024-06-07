#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.users.api.v1.views import UserPreference
from speleodb.users.api.v1.views import ObtainAuthToken

app_name = "user_api"

urlpatterns = [
    path("user/preferences/", UserPreference.as_view(), name="set_user_preferences"),
    path("user/auth-token/", ObtainAuthToken.as_view()),
]
