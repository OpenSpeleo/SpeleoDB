# -*- coding: utf-8 -*-

"""Tests for `gis-views` (list/create) and `gis-view-detail` (GET/PUT/PATCH/DELETE).

View lives in `speleodb/api/v2/views/gis_view_management.py`. GISView is
a user-owned saved view of one or more projects.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISView
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.users.models import User


def _create_gis_view(owner: User, name: str = "My View") -> GISView:
    return GISView.objects.create(
        owner=owner,
        name=name,
        description="Test view",
        allow_precise_zoom=False,
    )


@pytest.mark.django_db
class TestGISViewList(BaseAPITestCase):
    """GET /api/v2/user/gis_views/ - returns current user's views only."""

    def test_requires_authentication(self) -> None:
        response = self.client.get(reverse("api:v2:gis-views"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_returns_only_own_views(self) -> None:
        _ = _create_gis_view(self.user, name="Mine")
        other = UserFactory.create()
        _ = _create_gis_view(other, name="Theirs")

        response = self.client.get(
            reverse("api:v2:gis-views"), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        names = [v["name"] for v in response.data]
        assert "Mine" in names
        assert "Theirs" not in names

    def test_empty_list(self) -> None:
        response = self.client.get(
            reverse("api:v2:gis-views"), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data == []


@pytest.mark.django_db
class TestGISViewCreate(BaseAPIProjectTestCase):
    """POST /api/v2/user/gis_views/ - create new GIS view."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_ONLY, permission_type=PermissionType.USER
        )
        self.url = reverse("api:v2:gis-views")

    def test_requires_authentication(self) -> None:
        response = self.client.post(
            self.url,
            {
                "name": "X",
                "description": "",
                "allow_precise_zoom": False,
                "projects": [],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_minimal(self) -> None:
        response = self.client.post(
            self.url,
            {
                "name": "Empty",
                "description": "No projects",
                "allow_precise_zoom": False,
                "projects": [],
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data["name"] == "Empty"
        assert GISView.objects.filter(owner=self.user, name="Empty").exists()

    def test_create_with_project(self) -> None:
        response = self.client.post(
            self.url,
            {
                "name": "With project",
                "description": "",
                "allow_precise_zoom": True,
                "projects": [
                    {"project_id": str(self.project.id), "use_latest": True},
                ],
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data
        gv = GISView.objects.get(owner=self.user, name="With project")
        assert gv.allow_precise_zoom is True
        assert gv.project_views.count() == 1

    def test_create_rejects_inaccessible_project(self) -> None:
        stranger_project = ProjectFactory.create()
        response = self.client.post(
            self.url,
            {
                "name": "Bad",
                "description": "",
                "allow_precise_zoom": False,
                "projects": [
                    {"project_id": str(stranger_project.id), "use_latest": True}
                ],
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_create_rejects_duplicate_projects(self) -> None:
        response = self.client.post(
            self.url,
            {
                "name": "Dup",
                "description": "",
                "allow_precise_zoom": False,
                "projects": [
                    {"project_id": str(self.project.id), "use_latest": True},
                    {"project_id": str(self.project.id), "use_latest": True},
                ],
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data


@pytest.mark.django_db
class TestGISViewDetail(BaseAPITestCase):
    """GET /api/v2/user/gis_views/<id>/ - owner only."""

    def test_owner_can_read(self) -> None:
        view = _create_gis_view(self.user, name="Hello")
        response = self.client.get(
            reverse("api:v2:gis-view-detail", kwargs={"id": view.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data["name"] == "Hello"

    def test_stranger_cannot_read(self) -> None:
        other = UserFactory.create()
        view = _create_gis_view(other, name="Theirs")

        response = self.client.get(
            reverse("api:v2:gis-view-detail", kwargs={"id": view.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_404_for_unknown_id(self) -> None:
        response = self.client.get(
            reverse("api:v2:gis-view-detail", kwargs={"id": uuid.uuid4()}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestGISViewUpdate(BaseAPIProjectTestCase):
    """PUT / PATCH on detail endpoint."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_ONLY, permission_type=PermissionType.USER
        )
        self.view = _create_gis_view(self.user, name="Initial")
        self.url = reverse("api:v2:gis-view-detail", kwargs={"id": self.view.id})

    def test_patch_updates_name(self) -> None:
        response = self.client.patch(
            self.url,
            {"name": "Renamed"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        self.view.refresh_from_db()
        assert self.view.name == "Renamed"

    def test_put_replaces_projects(self) -> None:
        response = self.client.put(
            self.url,
            {
                "name": "New",
                "description": "",
                "allow_precise_zoom": False,
                "projects": [{"project_id": str(self.project.id), "use_latest": True}],
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        self.view.refresh_from_db()
        assert self.view.project_views.count() == 1

    def test_stranger_cannot_update(self) -> None:
        other = UserFactory.create()
        other_view = _create_gis_view(other, name="Theirs")
        response = self.client.patch(
            reverse("api:v2:gis-view-detail", kwargs={"id": other_view.id}),
            {"name": "Hacked"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestGISViewDelete(BaseAPITestCase):
    """DELETE on detail endpoint."""

    def test_owner_can_delete(self) -> None:
        view = _create_gis_view(self.user, name="Gone")
        view_id = view.id
        response = self.client.delete(
            reverse("api:v2:gis-view-detail", kwargs={"id": view_id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert not GISView.objects.filter(id=view_id).exists()

    def test_stranger_cannot_delete(self) -> None:
        other = UserFactory.create()
        view = _create_gis_view(other, name="Theirs")
        response = self.client.delete(
            reverse("api:v2:gis-view-detail", kwargs={"id": view.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert GISView.objects.filter(id=view.id).exists()
