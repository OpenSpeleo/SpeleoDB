#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.api.v1.views.project import CreateProjectApiView
from speleodb.api.v1.views.project import ProjectApiView
from speleodb.api.v1.views.project import ProjectListApiView
from speleodb.api.v1.views.project_explorer import ProjectRevisionsApiView

urlpatterns = [
    path("project/", CreateProjectApiView.as_view(), name="create_project"),
    path("projects/", ProjectListApiView.as_view(), name="list_all_projects"),
    path("project/<uuid:id>/", ProjectApiView.as_view(), name="one_project_apiview"),
    path(
        "project/<uuid:id>/revisions/",
        ProjectRevisionsApiView.as_view(),
        name="one_project_revisions_apiview",
    ),
]
