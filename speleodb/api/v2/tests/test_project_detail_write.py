# -*- coding: utf-8 -*-

"""Tests for the write methods (PUT / PATCH / DELETE) on `project-detail`.

The GET branch is already covered in `test_project_api.py`; these tests
pin the mutation branches that Phase 1 left uncovered.

View: `speleodb/api/v2/views/project.py::ProjectSpecificApiView`.
"""

from __future__ import annotations

import uuid

import pytest
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import Project


@pytest.mark.django_db
class TestProjectDetailPatch(BaseAPIProjectTestCase):
    """PATCH with WRITE access updates a subset of fields."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        self.url = reverse("api:v2:project-detail", kwargs={"id": self.project.id})

    def test_requires_authentication(self) -> None:
        response = self.client.patch(self.url, {"name": "x"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patch_name_happy_path(self) -> None:
        response = self.client.patch(
            self.url,
            {"name": "Renamed"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        self.project.refresh_from_db()
        assert self.project.name == "Renamed"

    def test_patch_description(self) -> None:
        response = self.client.patch(
            self.url,
            {"description": "A new description"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        self.project.refresh_from_db()
        assert self.project.description == "A new description"

    def test_patch_rejected_for_read_only(self) -> None:
        """A user with only READ_ONLY should not be able to mutate."""
        # Create a fresh project with only READ_ONLY access for this user.
        read_only_project = Project.objects.create(
            name="ReadOnly",
            description="ro",
            created_by=self.user.email,
        )
        # Give read-only on the new project directly.
        UserProjectPermissionFactory(
            target=self.user,
            level=PermissionLevel.READ_ONLY,
            project=read_only_project,
        )
        response = self.client.patch(
            reverse("api:v2:project-detail", kwargs={"id": read_only_project.id}),
            {"name": "hack"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestProjectDetailPut(BaseAPIProjectTestCase):
    """PUT replaces the whole project payload (requires WRITE)."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        self.url = reverse("api:v2:project-detail", kwargs={"id": self.project.id})

    def test_put_replaces(self) -> None:
        response = self.client.put(
            self.url,
            {
                "name": "PutName",
                "description": "replaced",
                "country": "FR",
                "type": self.project.type,
                "color": "#377eb8",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        self.project.refresh_from_db()
        assert self.project.name == "PutName"
        assert self.project.description == "replaced"


@pytest.mark.django_db
class TestProjectDetailDelete(BaseAPIProjectTestCase):
    """DELETE deactivates the project and all permissions (admin-only)."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN, permission_type=PermissionType.USER
        )
        self.url = reverse("api:v2:project-detail", kwargs={"id": self.project.id})

    def test_admin_can_delete(self) -> None:
        response = self.client.delete(self.url, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK, response.data
        self.project.refresh_from_db()
        assert self.project.is_active is False
        for perm in self.project.permissions:
            assert not perm.is_active

    def test_404_for_unknown_id(self) -> None:
        response = self.client.delete(
            reverse("api:v2:project-detail", kwargs={"id": uuid.uuid4()}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
