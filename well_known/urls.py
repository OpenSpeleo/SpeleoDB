# -*- coding: utf-8 -*-

from __future__ import annotations

from django.conf import settings
from django.urls import path
from django.views.decorators.cache import cache_page

from well_known.views import apple_app_site_association
from well_known.views import assetlinks
from well_known.views import change_password

app_name = "well_known"

urlpatterns = [
    path(
        "apple-app-site-association",
        apple_app_site_association
        if settings.DEBUG
        else cache_page(24 * 60 * 60)(apple_app_site_association),
        name="apple-app-site-association",
    ),
    path(
        "assetlinks.json",
        assetlinks if settings.DEBUG else cache_page(24 * 60 * 60)(assetlinks),
        name="assetlinks.json",
    ),
    path("change-password", change_password),
]
