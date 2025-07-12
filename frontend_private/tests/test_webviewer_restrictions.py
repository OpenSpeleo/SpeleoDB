# -*- coding: utf-8 -*-

from __future__ import annotations

from django.http import HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status
from rest_framework.authtoken.models import Token

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import UserPermissionFactory
from speleodb.surveys.models import PermissionLevel
from speleodb.users.tests.factories import UserFactory


class TestWebViewerRestrictions(TestCase):
    """
    Test that WEBVIEWER permission level is properly restricted in frontend_private.
    """

    def setUp(self) -> None:
        super().setUp()
        self.user = UserFactory.create()
        self.project_webviewer = ProjectFactory.create(created_by=self.user)
        self.project_readonly = ProjectFactory.create(created_by=self.user)
        self.project_readwrite = ProjectFactory.create(created_by=self.user)
        self.project_admin = ProjectFactory.create(created_by=self.user)

        # Create permissions
        UserPermissionFactory.create(
            target=self.user,
            project=self.project_webviewer,
            level=PermissionLevel.WEB_VIEWER,
        )
        UserPermissionFactory.create(
            target=self.user,
            project=self.project_readonly,
            level=PermissionLevel.READ_ONLY,
        )
        UserPermissionFactory.create(
            target=self.user,
            project=self.project_readwrite,
            level=PermissionLevel.READ_AND_WRITE,
        )
        UserPermissionFactory.create(
            target=self.user, project=self.project_admin, level=PermissionLevel.ADMIN
        )

        self.client.force_login(self.user)

    def test_project_listing_excludes_webviewer(self) -> None:
        """Test that projects with only WEBVIEWER access are not shown in listing."""
        url = reverse("private:projects")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK

        # Check that filtered_permissions is in context
        assert "filtered_permissions" in response.context
        filtered_permissions = response.context["filtered_permissions"]

        # Should have 3 projects (excluding WEBVIEWER)
        assert len(filtered_permissions) == 3  # noqa: PLR2004

        # WEBVIEWER project should not be in the list
        project_ids = [perm.project.id for perm in filtered_permissions]
        assert self.project_webviewer.id not in project_ids
        assert self.project_readonly.id in project_ids
        assert self.project_readwrite.id in project_ids
        assert self.project_admin.id in project_ids

    @parameterized.expand(
        [
            ("project_details",),
            ("project_user_permissions",),
            ("project_team_permissions",),
            ("project_mutexes",),
            ("project_revisions",),
            ("project_git_instructions",),
            ("project_upload",),
        ]
    )
    def test_webviewer_cannot_access_project_views(self, view_name: str) -> None:
        """Test that WEBVIEWER users cannot access any project views."""
        url = reverse(
            f"private:{view_name}", kwargs={"project_id": self.project_webviewer.id}
        )
        response = self.client.get(url)

        # Should redirect to projects listing
        assert isinstance(response, HttpResponseRedirect)
        assert response.status_code == status.HTTP_302_FOUND
        assert response.url == reverse("private:projects")

    @parameterized.expand(
        [
            (PermissionLevel.READ_ONLY,),
            (PermissionLevel.READ_AND_WRITE,),
            (PermissionLevel.ADMIN,),
        ]
    )
    def test_higher_permissions_can_access_project_views(
        self, level: PermissionLevel
    ) -> None:
        """
        Test that users with permissions higher than WEBVIEWER can access project views.
        """

        # Map permission level to project
        project_map = {
            PermissionLevel.READ_ONLY: self.project_readonly,
            PermissionLevel.READ_AND_WRITE: self.project_readwrite,
            PermissionLevel.ADMIN: self.project_admin,
        }
        project = project_map[level]

        url = reverse("private:project_details", kwargs={"project_id": project.id})
        response = self.client.get(url)

        # Should be successful
        assert response.status_code == status.HTTP_200_OK
        assert "project" in response.context
        assert response.context["project"].id == project.id

    def test_webviewer_can_still_access_geojson_api(self) -> None:
        """Test that WEBVIEWER users can still access the GeoJSON API."""

        token, _ = Token.objects.get_or_create(user=self.user)

        url = reverse(
            "api:v1:one_project_geojson_apiview",
            kwargs={"id": self.project_webviewer.id},
        )
        response = self.client.get(url, headers={"authorization": f"Token {token.key}"})

        assert response.status_code == status.HTTP_200_OK
