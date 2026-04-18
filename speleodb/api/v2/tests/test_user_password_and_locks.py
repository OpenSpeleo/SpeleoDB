# -*- coding: utf-8 -*-

"""Tests for `user-password-update` and `release-all-locks`.

Views live in `speleodb/api/v2/views/user.py`.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import ProjectMutex

# ============================================================================
# USER PASSWORD UPDATE
# ============================================================================


@pytest.mark.django_db
class TestUserPasswordUpdate(BaseAPITestCase):
    """PUT /api/v2/user/password/ -> change password."""

    def setUp(self) -> None:
        super().setUp()
        self.current_password = "OldPassword123!"  # noqa: S105
        self.user.set_password(self.current_password)
        self.user.save()
        self.url = reverse("api:v2:user-password-update")

    def test_requires_authentication(self) -> None:
        response = self.client.put(
            self.url,
            {
                "oldpassword": self.current_password,
                "password1": "NewPassword456!",
                "password2": "NewPassword456!",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_happy_path(self) -> None:
        response = self.client.put(
            self.url,
            {
                "oldpassword": self.current_password,
                "password1": "BrandNewPass789!",
                "password2": "BrandNewPass789!",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert "message" in response.data

        self.user.refresh_from_db()
        assert self.user.check_password("BrandNewPass789!")

    def test_wrong_old_password(self) -> None:
        response = self.client.put(
            self.url,
            {
                "oldpassword": "TotallyWrong",
                "password1": "BrandNewPass789!",
                "password2": "BrandNewPass789!",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "errors" in response.data

    def test_password_mismatch(self) -> None:
        response = self.client.put(
            self.url,
            {
                "oldpassword": self.current_password,
                "password1": "A-LongerPassword123!",
                "password2": "DIFFERENT-Password!",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "errors" in response.data

    def test_reuse_old_password_rejected(self) -> None:
        response = self.client.put(
            self.url,
            {
                "oldpassword": self.current_password,
                "password1": self.current_password,
                "password2": self.current_password,
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_weak_password_rejected(self) -> None:
        """Django's password validators should reject obviously weak inputs."""
        response = self.client.put(
            self.url,
            {
                "oldpassword": self.current_password,
                "password1": "short",
                "password2": "short",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data


# ============================================================================
# RELEASE ALL LOCKS
# ============================================================================


@pytest.mark.django_db
class TestReleaseAllUserLocks(BaseAPIProjectTestCase):
    """DELETE /api/v2/user/release_all_locks/ -> release every active mutex."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        self.url = reverse("api:v2:release-all-locks")

    def test_requires_authentication(self) -> None:
        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_releases_all_active_mutexes(self) -> None:
        # Seed a second project to ensure multiple mutexes are released.
        other_project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory(
            target=self.user,
            level=PermissionLevel.READ_AND_WRITE,
            project=other_project,
        )
        self.client.post(
            reverse("api:v2:project-acquire", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )
        self.client.post(
            reverse("api:v2:project-acquire", kwargs={"id": other_project.id}),
            headers={"authorization": self.auth},
        )

        # Both active mutexes should exist before the call.
        active_before = ProjectMutex.objects.filter(
            user=self.user, is_active=True
        ).count()
        assert active_before == 2  # noqa: PLR2004

        response = self.client.delete(self.url, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK, response.data

        # After release, all mutexes are deactivated for this user.
        active_after = ProjectMutex.objects.filter(
            user=self.user, is_active=True
        ).count()
        assert active_after == 0

    def test_releases_when_no_active_mutexes(self) -> None:
        """Calling the endpoint with zero active mutexes succeeds (no-op)."""
        response = self.client.delete(self.url, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK, response.data
