#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import re_path

from speleodb.surveys.api.v1.views import ProjectListApiView

urlpatterns = [
    # ========================== Public API Routes ========================== #
    # ================== Authentication Required API Routes ================= #
    re_path(r"^projects/$", ProjectListApiView.as_view()),
    # ================ Private API Routes - API KEY REQUIRED ================ #
]
