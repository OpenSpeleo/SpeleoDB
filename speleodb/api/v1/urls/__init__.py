#!/usr/bin/env python
# -*- coding: utf-8 -*-

from speleodb.api.v1.urls.file import urlpatterns as file_urlpatterns
from speleodb.api.v1.urls.mutex import urlpatterns as mutex_urlpatterns
from speleodb.api.v1.urls.permissions import urlpatterns as permissions_urlpatterns
from speleodb.api.v1.urls.project import urlpatterns as project_urlpatterns
from speleodb.api.v1.urls.team import urlpatterns as team_urlpatterns
from speleodb.api.v1.urls.user import urlpatterns as user_urlpatterns

app_name = "v1"

urlpatterns = (
    file_urlpatterns
    + mutex_urlpatterns
    + permissions_urlpatterns
    + project_urlpatterns
    + team_urlpatterns
    + user_urlpatterns
)
