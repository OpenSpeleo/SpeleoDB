"""Admin cannot bypass the geometry contract or overwrite another author's save."""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.contrib import admin
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status

from speleodb.common.enums import PermissionLevel
from speleodb.gis.admin.gis_geometry import GISGeometryAdmin
from speleodb.gis.geometry_services import create_gis_geometry
from speleodb.gis.geometry_services import update_gis_geometry
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISGeometryUserPermission
from speleodb.users.tests.factories import UserFactory

LINE: dict[str, Any] = {
    "type": "LineString",
    "coordinates": [[-87.5, 20.1], [-87.499, 20.1]],
}
UPDATED_REVISION = 2


@pytest.mark.django_db
def test_admin_creation_assigns_creator_access_and_validates_geojson() -> None:
    user = UserFactory.create(is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(user)
    url: str = reverse("admin:gis_gisgeometry_add")
    invalid = client.post(url, {"name": "Bad", "color": "#123456", "geojson": "{}"})
    assert invalid.status_code == status.HTTP_200_OK
    assert not GISGeometry.objects.exists()
    response = client.post(
        url, {"name": "Admin shape", "color": "#123456", "geojson": json.dumps(LINE)}
    )
    assert response.status_code == status.HTTP_302_FOUND
    geometry = GISGeometry.objects.get()
    assert geometry.created_by == user.email
    assert geometry.permissions.get(user=user).level == PermissionLevel.ADMIN
    assert geometry.revision == 1
    assert "created_by" in GISGeometryAdmin(GISGeometry, admin.site).readonly_fields


@pytest.mark.django_db
def test_admin_stale_edit_preserves_submitted_json_without_overwriting() -> None:
    user = UserFactory.create(is_staff=True, is_superuser=True)
    geometry = create_gis_geometry(GISGeometry(name="Original", geojson=LINE), user)
    client = Client()
    client.force_login(user)
    url: str = reverse("admin:gis_gisgeometry_change", args=[geometry.id])
    initial = client.get(url)
    assert 'name="expected_revision" value="1"' in initial.content.decode()
    update_gis_geometry(
        geometry_id=geometry.id,
        actor=user,
        expected_revision=1,
        updates={"name": "Other editor"},
    )
    response = client.post(
        url,
        {
            "name": "My draft",
            "color": "#123456",
            "geojson": json.dumps(LINE),
            "expected_revision": 1,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    assert "updated elsewhere" in response.content.decode()
    assert "My draft" in response.content.decode()
    geometry.refresh_from_db()
    assert geometry.name == "Other editor"
    assert geometry.revision == UPDATED_REVISION
    saved = client.post(
        url,
        {
            "name": "Fresh edit",
            "color": "#123456",
            "geojson": json.dumps(LINE),
            "expected_revision": 2,
        },
    )
    assert saved.status_code == status.HTTP_302_FOUND
    geometry.refresh_from_db()
    assert geometry.name == "Fresh edit"
    assert geometry.revision == UPDATED_REVISION + 1
    deleted = client.post(
        reverse("admin:gis_gisgeometry_delete", args=[geometry.id]), {"post": "yes"}
    )
    assert deleted.status_code == status.HTTP_403_FORBIDDEN
    assert GISGeometry.objects.filter(id=geometry.id).exists()


@pytest.mark.django_db
def test_admin_rejects_names_that_are_empty_after_sanitizing() -> None:
    user = UserFactory.create(is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(user)
    payload: dict[str, Any] = {
        "name": "<b></b>",
        "color": "#123456",
        "geojson": json.dumps(LINE),
    }
    response = client.post(reverse("admin:gis_gisgeometry_add"), payload)
    assert response.status_code == status.HTTP_200_OK
    assert "A name is required" in response.content.decode()
    assert not GISGeometry.objects.exists()
    geometry = create_gis_geometry(GISGeometry(name="Original", geojson=LINE), user)
    payload["expected_revision"] = 1
    response = client.post(
        reverse("admin:gis_gisgeometry_change", args=[geometry.id]), payload
    )
    assert response.status_code == status.HTTP_200_OK
    assert "A name is required" in response.content.decode()
    geometry.refresh_from_db()
    assert geometry.name == "Original"
    assert geometry.revision == 1


@pytest.mark.django_db
def test_admin_access_actions_are_soft_reversible_and_lock_the_geometry() -> None:
    user = UserFactory.create(is_staff=True, is_superuser=True)
    reader = UserFactory.create(email="admin-geometry-reader@example.com")
    geometry = create_gis_geometry(GISGeometry(name="Shared shape", geojson=LINE), user)
    permission = GISGeometryUserPermission.objects.create(
        user=reader, gis_geometry=geometry, level=PermissionLevel.READ_ONLY
    )
    client = Client()
    client.force_login(user)
    url: str = reverse("admin:permissions_gisgeometryuserpermissionproxy_changelist")
    for action, active in (("revoke_access", False), ("restore_access", True)):
        with CaptureQueriesContext(connection) as queries:
            response = client.post(
                url, {"action": action, "_selected_action": [permission.pk]}
            )
        assert response.status_code == status.HTTP_302_FOUND
        permission.refresh_from_db()
        assert permission.is_active is active
        assert permission.deactivated_by == (None if active else user)
        if connection.features.has_select_for_update:
            assert any(
                GISGeometry._meta.db_table in query["sql"]  # noqa: SLF001
                and "FOR UPDATE" in query["sql"]
                for query in queries
            )
    change_url: str = reverse(
        "admin:permissions_gisgeometryuserpermissionproxy_change", args=[permission.pk]
    )
    with CaptureQueriesContext(connection) as queries:
        response = client.post(change_url, {"level": PermissionLevel.READ_AND_WRITE})
    assert response.status_code == status.HTTP_302_FOUND
    if connection.features.has_select_for_update:
        assert any(
            GISGeometry._meta.db_table in query["sql"]  # noqa: SLF001
            and "FOR UPDATE" in query["sql"]
            for query in queries
        )
    permission.refresh_from_db()
    assert permission.level == PermissionLevel.READ_AND_WRITE
    geometry.refresh_from_db()
    assert geometry.revision == 1
    geometry.deactivate(user)
    response = client.post(
        url, {"action": "restore_access", "_selected_action": [permission.pk]}
    )
    assert response.status_code == status.HTTP_302_FOUND
    permission.refresh_from_db()
    assert not permission.is_active
