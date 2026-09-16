# -*- coding: utf-8 -*-

from __future__ import annotations

from django.http import HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.common.enums import PermissionLevel
from speleodb.testing.gitlab_pool import canonical_user
from speleodb.testing.gitlab_pool import project_matrix


class TestWebViewerRestrictions(TestCase):
    """
    Test that WEBVIEWER permission level is properly restricted in frontend_private.
    """

    def setUp(self) -> None:
        super().setUp()
        self.user = canonical_user("A")
        projects = project_matrix()
        self.project_webviewer = projects[PermissionLevel.WEB_VIEWER]
        self.project_readonly = projects[PermissionLevel.READ_ONLY]
        self.project_readwrite = projects[PermissionLevel.READ_AND_WRITE]
        self.project_admin = projects[PermissionLevel.ADMIN]

        self.client.force_login(self.user)

    def test_project_listing_excludes_webviewer(self) -> None:
        """Test that projects with only WEBVIEWER access are not shown in listing."""
        url = reverse("private:projects")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK

        # Check that projects_data is in context
        assert "projects_data" in response.context
        projects_data = response.context["projects_data"]

        # Should have 3 projects (excluding WEBVIEWER)
        assert len(projects_data) == 3  # noqa: PLR2004

        # WEBVIEWER project should not be in the list
        project_ids = [proj_data.project.id for proj_data in projects_data]
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
