# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.views.experiment import ExperimentApiView
from speleodb.api.v1.views.experiment import ExperimentSpecificApiView
from speleodb.api.v1.views.user_experiment_permission import (
    ExperimentUserPermissionListApiView,
)
from speleodb.api.v1.views.user_experiment_permission import (
    ExperimentUserPermissionSpecificApiView,
)

experiment_urlpatterns: list[URLPattern] = [
    path("", ExperimentSpecificApiView.as_view(), name="experiment-detail"),
    # --------- USER PERMISSIONS --------- #
    path(
        "permissions/",
        ExperimentUserPermissionListApiView.as_view(),
        name="experiment-user-permissions",
    ),
    path(
        "permission/detail/",
        ExperimentUserPermissionSpecificApiView.as_view(),
        name="experiment-user-permissions-detail",
    ),
]

urlpatterns: list[URLPattern | URLResolver] = [
    path("", ExperimentApiView.as_view(), name="experiments"),
    path("<uuid:id>/", include(experiment_urlpatterns)),
]
