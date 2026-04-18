# -*- coding: utf-8 -*-

"""Tests for `project-user-permissions` and `project-user-permissions-detail`.

Covers GET (list), POST (create / reactivate), PUT (update), DELETE
(deactivate) plus authz and validation failure paths. View lives in
`speleodb/api/v2/views/user_project_permission.py`.

Naming note: the "returns_403_for_anonymous" tests pin the real DRF behaviour
produced by `config/settings/base.py:572-578` — because `SessionAuthentication`
is the first default authenticator and returns `None` from
`authenticate_header`, DRF downgrades `NotAuthenticated` 401 -> 403. If the
auth-class ordering is ever changed (e.g. Token placed first), those tests
will need to flip to 401.
"""

from __future__ import annotations

import uuid

import pytest
from django.urls import reverse
from parameterized.parameterized import parameterized_class
from rest_framework import status
from rest_framework.authtoken.models import Token

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import UserProjectPermission
from speleodb.users.tests.factories import UserFactory


def _unique_email(prefix: str = "user") -> str:
    """Deterministically-unique email.

    `UserFactory.Meta.django_get_or_create = ["email"]` + `Faker("email")` can
    collide across two factory calls in the same test, causing subtle flakes
    (second UserFactory.create() returns the first user). Using a uuid4-suffix
    email guarantees distinct users.
    """
    return f"{prefix}-{uuid.uuid4()}@test.local"


# =============================================================================
# LIST endpoint (GET /api/v2/projects/<id>/permissions/user/)
# =============================================================================


@pytest.mark.django_db
class TestProjectUserPermissionList(BaseAPIProjectTestCase):
    """Any READ access may see the list."""

    def test_list_returns_403_for_anonymous(self) -> None:
        response = self.client.get(
            reverse("api:v2:project-user-permissions", kwargs={"id": self.project.id}),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.content

    def test_list_returns_403_for_malformed_token(self) -> None:
        response = self.client.get(
            reverse("api:v2:project-user-permissions", kwargs={"id": self.project.id}),
            headers={"authorization": "Token garbage-not-a-real-token"},
        )
        # DRF maps AuthenticationFailed to 401, but with
        # SessionAuthentication as first authenticator and no
        # WWW-Authenticate header, it may also surface as 403. Allow either —
        # the point is "not 200 and not 500".
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ), response.content

    def test_list_denied_without_project_permission(self) -> None:
        response = self.client.get(
            reverse("api:v2:project-user-permissions", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_list_succeeds_with_read_only_count_aware(self) -> None:
        """Read-only user sees exactly the active perms for THIS project."""
        # setUp gives self.user READ_ONLY via `set_test_project_permission`.
        self.set_test_project_permission(
            level=PermissionLevel.READ_ONLY, permission_type=PermissionType.USER
        )

        other_with_perm = UserFactory.create(email=_unique_email("other-perm"))
        UserProjectPermissionFactory.create(
            target=other_with_perm,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Noise: a third user with a perm on a DIFFERENT project, plus a
        # soft-deleted perm on this project. Neither should appear.
        noise_user = UserFactory.create(email=_unique_email("noise"))
        unrelated_project_perm = UserProjectPermissionFactory.create(target=noise_user)
        soft_deleted = UserProjectPermissionFactory.create(
            target=UserFactory.create(email=_unique_email("sd")),
            project=self.project,
            level=PermissionLevel.READ_ONLY,
        )
        soft_deleted.deactivate(deactivated_by=self.user)

        response = self.client.get(
            reverse("api:v2:project-user-permissions", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data["project"]["id"] == str(self.project.id), response.data

        emails = [perm["user"] for perm in response.data["permissions"]]
        assert self.user.email in emails, emails
        assert other_with_perm.email in emails, emails
        assert noise_user.email not in emails, emails
        assert soft_deleted.target.email not in emails, emails
        # exactly 2 active perms on this project
        assert len(response.data["permissions"]) == 2, response.data  # noqa: PLR2004

        # Unrelated perm still exists in DB, just not in this response.
        _ = unrelated_project_perm

    def test_list_returns_empty_permissions_when_only_team_perm(self) -> None:
        self.set_test_project_permission(
            level=PermissionLevel.READ_ONLY, permission_type=PermissionType.TEAM
        )
        response = self.client.get(
            reverse("api:v2:project-user-permissions", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        # Team grants access but creates no direct user permission row.
        assert response.data["permissions"] == [], response.data


# =============================================================================
# DETAIL endpoint — CREATE (POST)
# =============================================================================


@pytest.mark.django_db
class TestProjectUserPermissionCreate(BaseAPIProjectTestCase):
    """POST creates (or reactivates) a user permission. Admin-only."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN, permission_type=PermissionType.USER
        )
        self.target = UserFactory.create(email=_unique_email("target"))
        self.url = reverse(
            "api:v2:project-user-permissions-detail",
            kwargs={"id": self.project.id},
        )

    # ---- authz ----

    def test_post_returns_403_for_anonymous(self) -> None:
        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": "READ_ONLY"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_create_requires_admin_read_and_write_rejected(self) -> None:
        other = UserFactory.create(email=_unique_email("rw-caller"))
        _ = UserProjectPermissionFactory.create(
            target=other, project=self.project, level=PermissionLevel.READ_AND_WRITE
        )
        token, _ = Token.objects.get_or_create(user=other)
        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": "READ_ONLY"},
            format="json",
            headers={"authorization": f"Token {token.key}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_create_requires_admin_read_only_rejected(self) -> None:
        other = UserFactory.create(email=_unique_email("ro-caller"))
        _ = UserProjectPermissionFactory.create(
            target=other, project=self.project, level=PermissionLevel.READ_ONLY
        )
        token, _ = Token.objects.get_or_create(user=other)
        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": "READ_ONLY"},
            format="json",
            headers={"authorization": f"Token {token.key}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    # ---- happy path ----

    def test_create_happy_path(self) -> None:
        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": "READ_AND_WRITE"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data["permission"]["user"] == self.target.email, response.data
        assert response.data["permission"]["level"] == "READ_AND_WRITE", response.data

        perm = UserProjectPermission.objects.get(
            project=self.project, target=self.target, is_active=True
        )
        assert perm.level == PermissionLevel.READ_AND_WRITE, perm.level

    # ---- self-target guard ----

    def test_create_cannot_target_self(self) -> None:
        # `_process_request_data` raises NotAuthorizedError (401) when
        # request_user == target. This is the sole contract now that the
        # in-method 400 branches have been deleted (see
        # speleodb/api/v2/views/user_project_permission.py).
        response = self.client.post(
            self.url,
            {"user": self.user.email, "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.data
        assert "own permission" in str(response.data).lower(), response.data

    # ---- validation ----

    def test_create_rejects_unknown_user(self) -> None:
        response = self.client.post(
            self.url,
            {"user": "nobody@nowhere.test", "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data
        assert "does not exist" in str(response.data).lower(), response.data

    def test_create_rejects_inactive_target_user(self) -> None:
        inactive = UserFactory.create(email=_unique_email("inactive"))
        inactive.is_active = False
        inactive.save()
        response = self.client.post(
            self.url,
            {"user": inactive.email, "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        # `UserNotActiveError.status_code == HTTP_401_UNAUTHORIZED`.
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.data
        assert "inactive" in str(response.data).lower(), response.data

    def test_create_rejects_invalid_level(self) -> None:
        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": "BOGUS"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_create_rejects_empty_level(self) -> None:
        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": ""},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_create_rejects_whitespace_level(self) -> None:
        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": "   "},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_create_rejects_missing_level(self) -> None:
        # Missing body field now maps to HTTP 400 via `MissingFieldError`
        # (was a quirky 404 via `ValueNotFoundError` before the Phase-2 review
        # cleanup — see `speleodb/utils/exceptions.py`).
        response = self.client.post(
            self.url,
            {"user": self.target.email},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "missing" in str(response.data).lower(), response.data
        assert "level" in str(response.data).lower(), response.data

    def test_create_rejects_missing_user(self) -> None:
        response = self.client.post(
            self.url,
            {"level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "missing" in str(response.data).lower(), response.data
        assert "user" in str(response.data).lower(), response.data

    def test_create_rejects_empty_body(self) -> None:
        response = self.client.post(
            self.url,
            {},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "missing" in str(response.data).lower(), response.data

    # ---- duplicate / reactivation ----

    def test_create_duplicate_active_fails(self) -> None:
        _ = UserProjectPermissionFactory.create(
            target=self.target,
            project=self.project,
            level=PermissionLevel.READ_ONLY,
        )
        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": "READ_AND_WRITE"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "already exist" in str(response.data).lower(), response.data

    def test_create_reactivates_deactivated_permission(self) -> None:
        perm = UserProjectPermissionFactory.create(
            target=self.target,
            project=self.project,
            level=PermissionLevel.READ_ONLY,
        )
        perm.deactivate(deactivated_by=self.user)
        # No second `perm.save()` here — `deactivate()` already saves (see
        # `speleodb/surveys/models/permission_base.py:46-49`).
        assert not perm.is_active
        assert perm.deactivated_by == self.user

        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": "READ_AND_WRITE"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data

        perm.refresh_from_db()
        assert perm.is_active
        assert perm.level == PermissionLevel.READ_AND_WRITE
        # Audit trail: reactivate() clears deactivated_by.
        assert perm.deactivated_by is None, perm.deactivated_by


# =============================================================================
# DETAIL endpoint — UPDATE (PUT)
# =============================================================================


@pytest.mark.django_db
class TestProjectUserPermissionUpdate(BaseAPIProjectTestCase):
    """PUT updates an existing user permission's level."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN, permission_type=PermissionType.USER
        )
        self.target = UserFactory.create(email=_unique_email("target-put"))
        self.existing = UserProjectPermissionFactory.create(
            target=self.target,
            project=self.project,
            level=PermissionLevel.READ_ONLY,
        )
        self.url = reverse(
            "api:v2:project-user-permissions-detail",
            kwargs={"id": self.project.id},
        )

    def test_put_returns_403_for_anonymous(self) -> None:
        response = self.client.put(
            self.url,
            {"user": self.target.email, "level": "READ_AND_WRITE"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_put_requires_admin(self) -> None:
        other = UserFactory.create(email=_unique_email("rw-put"))
        _ = UserProjectPermissionFactory.create(
            target=other, project=self.project, level=PermissionLevel.READ_AND_WRITE
        )
        token, _ = Token.objects.get_or_create(user=other)
        response = self.client.put(
            self.url,
            {"user": self.target.email, "level": "READ_AND_WRITE"},
            format="json",
            headers={"authorization": f"Token {token.key}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_put_updates_level(self) -> None:
        response = self.client.put(
            self.url,
            {"user": self.target.email, "level": "READ_AND_WRITE"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data["permission"]["level"] == "READ_AND_WRITE", response.data

        self.existing.refresh_from_db()
        assert self.existing.level == PermissionLevel.READ_AND_WRITE

    def test_put_cannot_target_self(self) -> None:
        response = self.client.put(
            self.url,
            {"user": self.user.email, "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.data
        assert "own permission" in str(response.data).lower(), response.data

    def test_put_404_when_no_active_permission(self) -> None:
        stranger = UserFactory.create(email=_unique_email("stranger-put"))
        response = self.client.put(
            self.url,
            {"user": stranger.email, "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    def test_put_404_when_permission_is_soft_deleted(self) -> None:
        """PUT on a soft-deleted perm must 404 (not silently reactivate)."""
        self.existing.deactivate(deactivated_by=self.user)
        assert not self.existing.is_active

        response = self.client.put(
            self.url,
            {"user": self.target.email, "level": "READ_AND_WRITE"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    def test_put_rejects_missing_level(self) -> None:
        response = self.client.put(
            self.url,
            {"user": self.target.email},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "missing" in str(response.data).lower(), response.data

    def test_put_rejects_missing_user(self) -> None:
        response = self.client.put(
            self.url,
            {"level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data


# =============================================================================
# DETAIL endpoint — DELETE
# =============================================================================


@pytest.mark.django_db
class TestProjectUserPermissionDelete(BaseAPIProjectTestCase):
    """DELETE deactivates an existing user permission."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN, permission_type=PermissionType.USER
        )
        self.target = UserFactory.create(email=_unique_email("target-del"))
        self.existing = UserProjectPermissionFactory.create(
            target=self.target,
            project=self.project,
            level=PermissionLevel.READ_ONLY,
        )
        self.url = reverse(
            "api:v2:project-user-permissions-detail",
            kwargs={"id": self.project.id},
        )

    def test_delete_returns_403_for_anonymous(self) -> None:
        response = self.client.delete(
            self.url,
            {"user": self.target.email},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_delete_requires_admin(self) -> None:
        other = UserFactory.create(email=_unique_email("rw-del"))
        _ = UserProjectPermissionFactory.create(
            target=other, project=self.project, level=PermissionLevel.READ_AND_WRITE
        )
        token, _ = Token.objects.get_or_create(user=other)
        response = self.client.delete(
            self.url,
            {"user": self.target.email},
            format="json",
            headers={"authorization": f"Token {token.key}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_delete_deactivates(self) -> None:
        response = self.client.delete(
            self.url,
            {"user": self.target.email},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data

        self.existing.refresh_from_db()
        assert not self.existing.is_active
        assert self.existing.deactivated_by == self.user, self.existing.deactivated_by

    def test_delete_cannot_target_self(self) -> None:
        response = self.client.delete(
            self.url,
            {"user": self.user.email},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.data
        assert "own permission" in str(response.data).lower(), response.data

    def test_delete_404_when_no_active_permission(self) -> None:
        stranger = UserFactory.create(email=_unique_email("stranger-del"))
        response = self.client.delete(
            self.url,
            {"user": stranger.email},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    def test_delete_is_idempotent_second_call_returns_404(self) -> None:
        """Second DELETE on the same target returns 404, not 500."""
        response1 = self.client.delete(
            self.url,
            {"user": self.target.email},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response1.status_code == status.HTTP_200_OK, response1.data

        response2 = self.client.delete(
            self.url,
            {"user": self.target.email},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response2.status_code == status.HTTP_404_NOT_FOUND, response2.data

    def test_delete_rejects_missing_user(self) -> None:
        response = self.client.delete(
            self.url,
            {},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "missing" in str(response.data).lower(), response.data


# =============================================================================
# MATRIX: list-endpoint access across (level, permission_type)
# =============================================================================


@parameterized_class(
    [
        {
            "level": PermissionLevel.WEB_VIEWER,
            "permission_type": PermissionType.USER,
            "expected_status": status.HTTP_403_FORBIDDEN,
        },
        {
            "level": PermissionLevel.READ_ONLY,
            "permission_type": PermissionType.USER,
            "expected_status": status.HTTP_200_OK,
        },
        {
            "level": PermissionLevel.READ_AND_WRITE,
            "permission_type": PermissionType.USER,
            "expected_status": status.HTTP_200_OK,
        },
        {
            "level": PermissionLevel.ADMIN,
            "permission_type": PermissionType.USER,
            "expected_status": status.HTTP_200_OK,
        },
        {
            "level": PermissionLevel.READ_ONLY,
            "permission_type": PermissionType.TEAM,
            "expected_status": status.HTTP_200_OK,
        },
        {
            "level": PermissionLevel.READ_AND_WRITE,
            "permission_type": PermissionType.TEAM,
            "expected_status": status.HTTP_200_OK,
        },
    ]
)
@pytest.mark.django_db
class TestProjectUserPermissionListMatrix(BaseAPIProjectTestCase):
    """List endpoint access matrix."""

    level: PermissionLevel
    permission_type: PermissionType
    expected_status: int

    def test_list_access_matrix(self) -> None:
        self.set_test_project_permission(
            level=self.level, permission_type=self.permission_type
        )
        response = self.client.get(
            reverse("api:v2:project-user-permissions", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == self.expected_status, response.data


# =============================================================================
# MATRIX: detail-endpoint (POST) admin-only access across (level, permission_type)
# =============================================================================


@parameterized_class(
    [
        {
            "level": PermissionLevel.WEB_VIEWER,
            "permission_type": PermissionType.USER,
            "expected_status": status.HTTP_403_FORBIDDEN,
        },
        {
            "level": PermissionLevel.READ_ONLY,
            "permission_type": PermissionType.USER,
            "expected_status": status.HTTP_403_FORBIDDEN,
        },
        {
            "level": PermissionLevel.READ_AND_WRITE,
            "permission_type": PermissionType.USER,
            "expected_status": status.HTTP_403_FORBIDDEN,
        },
        {
            "level": PermissionLevel.ADMIN,
            "permission_type": PermissionType.USER,
            "expected_status": status.HTTP_201_CREATED,
        },
        {
            "level": PermissionLevel.READ_ONLY,
            "permission_type": PermissionType.TEAM,
            "expected_status": status.HTTP_403_FORBIDDEN,
        },
        {
            "level": PermissionLevel.READ_AND_WRITE,
            "permission_type": PermissionType.TEAM,
            "expected_status": status.HTTP_403_FORBIDDEN,
        },
    ]
)
@pytest.mark.django_db
class TestProjectUserPermissionDetailPostMatrix(BaseAPIProjectTestCase):
    """Detail-endpoint POST (grant permission) — admin-only."""

    level: PermissionLevel
    permission_type: PermissionType
    expected_status: int

    def test_post_access_matrix(self) -> None:
        self.set_test_project_permission(
            level=self.level, permission_type=self.permission_type
        )
        target = UserFactory.create(email=_unique_email("matrix-target"))
        response = self.client.post(
            reverse(
                "api:v2:project-user-permissions-detail",
                kwargs={"id": self.project.id},
            ),
            {"user": target.email, "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == self.expected_status, response.data
