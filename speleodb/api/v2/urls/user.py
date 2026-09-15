# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import path

from speleodb.api.v2.views.gis_view_management import GISViewManagementDetailApiView
from speleodb.api.v2.views.gis_view_management import GISViewManagementListApiView
from speleodb.api.v2.views.user import ReleaseAllUserLocksView
from speleodb.api.v2.views.user import UserAuthTokenView
from speleodb.api.v2.views.user import UserAutocompleteView
from speleodb.api.v2.views.user import UserInfo
from speleodb.api.v2.views.user import UserPasswordChangeView
from speleodb.api.v2.views.user_dashboard import UserDashboardStatsView
from speleodb.api.v2.views.user_export import UserExportDetailView
from speleodb.api.v2.views.user_export import UserExportDownloadView
from speleodb.api.v2.views.user_export import UserExportListView
from speleodb.api.v2.views.user_export import UserExportRetryView

urlpatterns: list[URLPattern] = [
    path("exports/", UserExportListView.as_view(), name="user-exports"),
    path(
        "exports/<uuid:id>/", UserExportDetailView.as_view(), name="user-export-detail"
    ),
    path(
        "exports/<uuid:id>/retry/",
        UserExportRetryView.as_view(),
        name="user-export-retry",
    ),
    path(
        "exports/<uuid:id>/download/",
        UserExportDownloadView.as_view(),
        name="user-export-download",
    ),
    path("", UserInfo.as_view(), name="user-detail"),
    path("auth-token/", UserAuthTokenView.as_view(), name="user-auth-token"),
    path("password/", UserPasswordChangeView.as_view(), name="user-password-update"),
    path(
        "release_all_locks/",
        ReleaseAllUserLocksView.as_view(),
        name="release-all-locks",
    ),
    path("autocomplete/", UserAutocompleteView.as_view(), name="user-autocomplete"),
    path(
        "dashboard-stats/",
        UserDashboardStatsView.as_view(),
        name="user-dashboard-stats",
    ),
    # GIS View Management
    path("gis_views/", GISViewManagementListApiView.as_view(), name="gis-views"),
    path(
        "gis_views/<uuid:id>/",
        GISViewManagementDetailApiView.as_view(),
        name="gis-view-detail",
    ),
]
