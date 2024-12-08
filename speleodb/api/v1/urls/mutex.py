#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.api.v1.views.mutex import ProjectAcquireApiView
from speleodb.api.v1.views.mutex import ProjectReleaseApiView

urlpatterns = [
    path(
        "project/<uuid:id>/acquire/",
        ProjectAcquireApiView.as_view(),
        name="acquire_project",
    ),
    path(
        "project/<uuid:id>/release/",
        ProjectReleaseApiView.as_view(),
        name="release_project",
    ),
]
