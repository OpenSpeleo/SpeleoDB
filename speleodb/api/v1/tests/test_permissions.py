# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.surveys.models import PermissionLevel


class TestPermissionsApiView(BaseAPIProjectTestCase):
    """Test suite to verify the permission level of API endpoints."""

    @parameterized.expand([PermissionType.USER, PermissionType.TEAM])
    def test_webviewer_cannot_access_other_endpoints(
        self, permission_type: PermissionType
    ) -> None:
        """Test that WEB_VIEWER permission only grants access to GeoJSON endpoint."""
        self.set_test_project_permission(
            level=PermissionLevel.WEB_VIEWER, permission_type=permission_type
        )

        auth = self.header_prefix + self.token.key

        # Test that WEB_VIEWER cannot access the main project details
        response = self.client.get(
            reverse("api:v1:project-detail", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Test that WEB_VIEWER cannot acquire project mutex
        response = self.client.post(
            reverse("api:v1:project-acquire", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Test that WEB_VIEWER cannot release project mutex
        response = self.client.post(
            reverse("api:v1:project-release", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Test that WEB_VIEWER cannot access revisions
        response = self.client.get(
            reverse("api:v1:project-revisions", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # But WEB_VIEWER CAN access GeoJSON
        response = self.client.get(
            reverse("api:v1:project-geojson", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )
        assert response.status_code == status.HTTP_200_OK
