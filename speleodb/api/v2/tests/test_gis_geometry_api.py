"""Real permission and persistence boundaries for private geometry authoring."""

from __future__ import annotations

from typing import Any

import pytest
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.gis_geometry_access import accessible_gis_geometries_queryset
from speleodb.api.v2.serializers.gis_geometry import GISGeometryListSerializer
from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.common.enums import PermissionLevel
from speleodb.gis.geometry_services import create_gis_geometry
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISGeometryUserPermission
from speleodb.users.tests.factories import UserFactory

LINE: dict[str, Any] = {
    "type": "LineString",
    "coordinates": [[-87.5, 20.1], [-87.499, 20.1]],
}
EXTRA_GEOMETRY_COUNT = 4
UPDATED_REVISION = 2


@pytest.mark.django_db
class TestGISGeometryAPI(BaseAPITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.geometry = create_gis_geometry(
            GISGeometry(name="Cave entrance", geojson=LINE, color="#377eb8"), self.user
        )
        self.detail_url = reverse(
            "api:v2:gis-geometry-detail", kwargs={"id": self.geometry.id}
        )
        self.permission_url = reverse(
            "api:v2:gis-geometry-permissions", kwargs={"id": self.geometry.id}
        )
        self.list_url = reverse("api:v2:gis-geometry-list")
        self.client.force_authenticate(user=self.user)

    def test_create_assigns_creator_and_admin_and_ignores_lifecycle_input(self) -> None:
        response = self.client.post(
            self.list_url,
            {
                "name": "New shape",
                "color": "#ABCDEF",
                "geojson": LINE,
                "created_by": "spoof@example.com",
                "revision": 800,
                "is_active": False,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        geometry = GISGeometry.objects.get(id=response.data["id"])
        assert geometry.created_by == self.user.email
        assert geometry.revision == 1
        assert geometry.is_active
        assert geometry.color == "#abcdef"
        assert geometry.permissions.get(user=self.user).level == PermissionLevel.ADMIN
        assert response.data["can_write"] is True
        assert response.data["can_manage_permissions"] is True
        assert response.data["bbox_area_m2"] == 0
        assert response.data["vertex_count"] == len(LINE["coordinates"])
        assert "source_format" not in response.data

    def test_hidden_layer_listing_is_metadata_only_and_constant_query(self) -> None:
        stranger = UserFactory.create(email="geometry-noise@example.com")
        create_gis_geometry(GISGeometry(name="Private noise", geojson=LINE), stranger)
        for index in range(EXTRA_GEOMETRY_COUNT):
            create_gis_geometry(
                GISGeometry(name=f"Geometry {index}", geojson=LINE), self.user
            )
        with self.assertNumQueries(1):
            data = GISGeometryListSerializer(
                accessible_gis_geometries_queryset(self.user).defer("geojson"),
                many=True,
            ).data
        assert len(data) == EXTRA_GEOMETRY_COUNT + 1
        assert all(item["geometry_type"] == "LineString" for item in data)
        assert all("geojson" not in item for item in data)
        assert all(
            item["user_permission_level"] == PermissionLevel.ADMIN for item in data
        )
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == EXTRA_GEOMETRY_COUNT + 1

    def test_geometry_update_requires_revision_and_rejects_stale_save(self) -> None:
        missing = self.client.patch(self.detail_url, {"name": "Missing"}, format="json")
        assert missing.status_code == status.HTTP_400_BAD_REQUEST
        assert "expected_revision" in missing.data["errors"]
        updated = self.client.patch(
            self.detail_url,
            {"name": "First writer", "expected_revision": 1},
            format="json",
        )
        assert updated.status_code == status.HTTP_200_OK
        assert updated.data["revision"] == UPDATED_REVISION
        stale = self.client.patch(
            self.detail_url,
            {"name": "Stale writer", "expected_revision": 1},
            format="json",
        )
        assert stale.status_code == status.HTTP_409_CONFLICT
        assert stale.data["code"] == "GIS_GEOMETRY_CONFLICT"
        self.geometry.refresh_from_db()
        assert self.geometry.name == "First writer"
        assert self.geometry.revision == UPDATED_REVISION

    def test_invalid_raw_geojson_does_not_partially_save_metadata(self) -> None:
        response = self.client.patch(
            self.detail_url,
            {
                "name": "Should not save",
                "expected_revision": 1,
                "geojson": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "30 km²" in str(response.data["errors"]["geojson"])
        self.geometry.refresh_from_db()
        assert self.geometry.name == "Cave entrance"
        assert self.geometry.geojson == LINE
        assert self.geometry.revision == 1

    def test_read_write_admin_permission_matrix(self) -> None:
        for level in PermissionLevel.members_no_webviewer:
            with self.subTest(level=level):
                user = UserFactory.create(
                    email=f"geometry-level-{level.value}@example.com"
                )
                GISGeometryUserPermission.objects.create(
                    user=user, gis_geometry=self.geometry, level=level
                )
                self.client.force_authenticate(user=user)
                detail = self.client.get(self.detail_url)
                assert detail.status_code == status.HTTP_200_OK
                assert detail.data["can_write"] is (
                    level >= PermissionLevel.READ_AND_WRITE
                )
                assert detail.data["can_delete"] is (level == PermissionLevel.ADMIN)
                assert (
                    self.client.get(self.permission_url).status_code
                    == status.HTTP_200_OK
                )
                self.geometry.refresh_from_db()
                edit = self.client.patch(
                    self.detail_url,
                    {"name": "Updated", "expected_revision": self.geometry.revision},
                    format="json",
                )
                assert edit.status_code == (
                    status.HTTP_200_OK
                    if level >= PermissionLevel.READ_AND_WRITE
                    else status.HTTP_403_FORBIDDEN
                )
                if level != PermissionLevel.ADMIN:
                    assert (
                        self.client.delete(self.detail_url).status_code
                        == status.HTTP_403_FORBIDDEN
                    )
                    for method in ("post", "put", "delete"):
                        response = getattr(self.client, method)(
                            self.permission_url,
                            {"user": self.user.email, "level": "READ_ONLY"},
                            format="json",
                        )
                        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unrelated_revoked_inactive_and_anonymous_have_no_access(self) -> None:
        stranger = UserFactory.create(email="geometry-stranger@example.com")
        self.client.force_authenticate(user=stranger)
        assert self.client.get(self.list_url).data == []
        assert self.client.get(self.detail_url).status_code == status.HTTP_404_NOT_FOUND
        permission = GISGeometryUserPermission.objects.create(
            user=stranger, gis_geometry=self.geometry, level=PermissionLevel.ADMIN
        )
        permission.deactivate(self.user)
        assert self.client.get(self.detail_url).status_code == status.HTTP_404_NOT_FOUND
        self.client.force_authenticate(user=self.user)
        assert self.client.delete(self.detail_url).status_code == status.HTTP_200_OK
        assert self.client.get(self.detail_url).status_code == status.HTTP_404_NOT_FOUND
        assert (
            self.client.get(self.permission_url).status_code
            == status.HTTP_404_NOT_FOUND
        )
        assert self.client.get(self.list_url).data == []
        self.client.force_authenticate(user=None)
        assert self.client.get(self.list_url).status_code == status.HTTP_403_FORBIDDEN
        assert (
            self.client.post(
                self.list_url, {"name": "No", "geojson": LINE}, format="json"
            ).status_code
            == status.HTTP_403_FORBIDDEN
        )

    def test_permission_lifecycle_does_not_change_content_revision(self) -> None:
        collaborator = UserFactory.create(email="geometry-collaborator@example.com")
        payload: dict[str, str] = {
            "user": collaborator.email,
            "level": "READ_AND_WRITE",
        }
        grant = self.client.post(self.permission_url, payload, format="json")
        assert grant.status_code == status.HTTP_201_CREATED
        assert grant.data["gis_geometry"]["revision"] == 1
        assert (
            self.client.post(self.permission_url, payload, format="json").status_code
            == status.HTTP_400_BAD_REQUEST
        )
        payload["level"] = "ADMIN"
        assert (
            self.client.put(self.permission_url, payload, format="json").status_code
            == status.HTTP_200_OK
        )
        revoke = self.client.delete(self.permission_url, payload, format="json")
        assert revoke.status_code == status.HTTP_200_OK
        assert (
            self.client.delete(self.permission_url, payload, format="json").status_code
            == status.HTTP_404_NOT_FOUND
        )
        assert (
            self.client.put(self.permission_url, payload, format="json").status_code
            == status.HTTP_404_NOT_FOUND
        )
        permission = self.geometry.permissions.get(user=collaborator)
        assert not permission.is_active
        assert permission.deactivated_by == self.user
        assert (
            self.client.post(self.permission_url, payload, format="json").status_code
            == status.HTTP_201_CREATED
        )
        permission.refresh_from_db()
        assert permission.is_active
        assert permission.deactivated_by is None
        assert set(self.geometry.permissions.values_list("user_id", flat=True)) == {
            self.user.id,
            collaborator.id,
        }
        self.geometry.refresh_from_db()
        assert self.geometry.revision == 1

    def test_permissions_reject_self_and_invalid_payloads(self) -> None:
        collaborator = UserFactory.create(email="geometry-invalid@example.com")
        for method in ("post", "put", "delete"):
            response = getattr(self.client, method)(
                self.permission_url,
                {"user": self.user.email, "level": "READ_ONLY"},
                format="json",
            )
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
        invalid_payloads: tuple[Any, ...] = (
            {},
            [],
            {"user": collaborator.email},
            {"user": collaborator.email, "level": "WEB_VIEWER"},
            {"user": collaborator.email, "level": 3},
        )
        for payload in invalid_payloads:
            response = self.client.post(self.permission_url, payload, format="json")
            assert response.status_code == status.HTTP_400_BAD_REQUEST
        collaborator.is_active = False
        collaborator.save(update_fields=["is_active"])
        response = self.client.post(
            self.permission_url,
            {"user": collaborator.email, "level": "READ_ONLY"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
