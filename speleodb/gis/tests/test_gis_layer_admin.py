# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import cast

import pytest
from django.contrib import admin
from django.test import RequestFactory

from speleodb.gis.admin.gis_layer import GISLayerAdmin
from speleodb.gis.models import GISLayer
from speleodb.permissions.admin.gis_layer import GISLayerUserPermissionAdmin
from speleodb.permissions.admin.gis_layer import GISLayerUserPermissionProxy
from speleodb.users.tests.factories import UserFactory


@pytest.mark.django_db
def test_admin_cannot_hard_delete_or_bypass_layer_lifecycle() -> None:
    user = UserFactory.create(is_staff=True, is_superuser=True)
    request = RequestFactory().get("/admin/")
    request.user = user
    layer_admin = GISLayerAdmin(GISLayer, admin.site)
    permission_admin = GISLayerUserPermissionAdmin(
        GISLayerUserPermissionProxy,
        admin.site,
    )

    assert layer_admin.has_delete_permission(request) is False
    assert layer_admin.has_add_permission(request) is False
    assert permission_admin.has_delete_permission(request) is False
    assert "created_by" in layer_admin.readonly_fields
    assert "is_active" in layer_admin.readonly_fields
    assert {"is_active", "deactivated_by"} <= set(
        permission_admin.get_readonly_fields(request)
    )


@pytest.mark.django_db
def test_existing_permission_identity_is_immutable_in_admin() -> None:
    user = UserFactory.create(is_staff=True, is_superuser=True)
    request = RequestFactory().get("/admin/")
    request.user = user
    permission_admin = GISLayerUserPermissionAdmin(
        GISLayerUserPermissionProxy,
        admin.site,
    )

    assert {"user", "gis_layer"} <= set(
        permission_admin.get_readonly_fields(
            request,
            cast("GISLayerUserPermissionProxy", object()),
        )
    )
