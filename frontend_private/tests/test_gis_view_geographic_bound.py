from __future__ import annotations

import re
from typing import Any

from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseUserTestCaseMixin
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISGeometryUserPermission
from speleodb.gis.models import GISView


class GISViewGeographicBoundFrontendTest(BaseUserTestCaseMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)
        self.polygon = self.geometry("<Allowed polygon>")
        self.line = self.geometry("Line", polygon=False)
        self.hidden = self.geometry("Secret polygon", accessible=False)
        self.inactive = self.geometry("Inactive polygon", active=False)
        self.view = GISView.objects.create(
            name="Bounded view", owner=self.user, allow_precise_zoom=False
        )

    def geometry(
        self,
        name: str,
        *,
        polygon: bool = True,
        accessible: bool = True,
        active: bool = True,
    ) -> GISGeometry:
        geojson: dict[str, Any] = (
            {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0.01, 0], [0.01, 0.01], [0, 0.01], [0, 0]]],
            }
            if polygon
            else {"type": "LineString", "coordinates": [[0, 0], [0.01, 0.01]]}
        )
        geometry: GISGeometry = GISGeometry.objects.create(
            name=name,
            created_by=self.user.email,
            geojson=geojson,
            is_active=active,
        )
        if accessible:
            GISGeometryUserPermission.objects.create(
                user=self.user, gis_geometry=geometry, level=PermissionLevel.READ_ONLY
            )
        return geometry

    def details_url(self) -> str:
        return reverse("private:gis_view_details", kwargs={"gis_view_id": self.view.id})

    def test_new_and_edit_offer_only_active_accessible_polygons(self) -> None:
        for url in (reverse("private:gis_view_new"), self.details_url()):
            response = self.client.get(url)
            content: str = response.content.decode()
            assert response.status_code == status.HTTP_200_OK
            assert '<option value="">No geographic bound</option>' in content
            assert f'value="{self.polygon.id}"' in content
            assert "&lt;Allowed polygon&gt;" in content
            for excluded in (self.line, self.hidden, self.inactive):
                assert str(excluded.id) not in content
            assert "browser still downloads the full survey data" in content
            assert "OGC access is unchanged" in content

    def test_edit_preserves_selected_polygon(self) -> None:
        self.view.geographic_bound = self.polygon
        self.view.save()
        content: str = self.client.get(self.details_url()).content.decode()
        assert re.search(rf'<option\s+value="{self.polygon.id}"\s+selected', content)

    def test_revoked_bound_is_retained_without_disclosing_its_name(self) -> None:
        self.view.geographic_bound = self.polygon
        self.view.save()
        GISGeometryUserPermission.objects.filter(
            user=self.user, gis_geometry=self.polygon
        ).update(is_active=False)
        content: str = self.client.get(self.details_url()).content.decode()
        assert re.search(rf'<option\s+value="{self.polygon.id}"\s+selected', content)
        assert "Current geographic bound (access unavailable)" in content
        assert "Allowed polygon" not in content
        assert '<option value="">No geographic bound</option>' in content
