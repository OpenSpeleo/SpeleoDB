# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import path

from speleodb.api.v1.views.tools import ToolXLSToCompass
from speleodb.api.v1.views.tools import ToolXLSToDMP

urlpatterns: list[URLPattern] = [
    path("xls2dmp/", ToolXLSToDMP.as_view(), name="tool-xls2dmp"),
    path("xls2compass/", ToolXLSToCompass.as_view(), name="tool-xls2compass"),
]
