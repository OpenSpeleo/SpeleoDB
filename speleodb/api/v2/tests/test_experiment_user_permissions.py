# -*- coding: utf-8 -*-

"""Tests for `experiment-user-permissions` and
`experiment-user-permissions-detail`.

View lives in `speleodb/api/v2/views/user_experiment_permission.py`.

Contract notes:
- The experiment permission level field uses `choices_no_webviewer`, so
  `WEB_VIEWER` is rejected by `_process_request_data` with HTTP 400.
- Missing-body-field now returns HTTP 400 (`MissingFieldError`) — was 404
  via `ValueNotFoundError` before the Phase-2 review cleanup.
"""

from __future__ import annotations

import uuid

import pytest
from django.urls import reverse
from parameterized.parameterized import parameterized_class
from rest_framework import status
from rest_framework.authtoken.models import Token

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.factories import ExperimentFactory
from speleodb.api.v2.tests.factories import UserExperimentPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import ExperimentUserPermission
from speleodb.users.tests.factories import UserFactory


def _unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4()}@test.local"


# =============================================================================
# LIST endpoint
# =============================================================================


@pytest.mark.django_db
class TestExperimentUserPermissionList(BaseAPITestCase):
    """Any READ access sees the list."""

    def setUp(self) -> None:
        super().setUp()
        self.experiment = ExperimentFactory.create(created_by=self.user.email)
        self.url = reverse(
            "api:v2:experiment-user-permissions",
            kwargs={"id": self.experiment.id},
        )

    def test_list_returns_403_for_anonymous(self) -> None:
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.content

    def test_list_returns_403_for_malformed_token(self) -> None:
        response = self.client.get(
            self.url,
            headers={"authorization": "Token garbage-not-a-real-token"},
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ), response.content

    def test_list_requires_read_access(self) -> None:
        """Authenticated but no experiment perm -> 403."""
        response = self.client.get(self.url, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_list_success_count_aware(self) -> None:
        """List returns permissions for THIS experiment, cross-experiment isolated.

        IMPORTANT QUIRK: unlike `Project.user_permissions` which is a
        `@property` that filters `is_active=True`
        (`speleodb/surveys/models/project.py:388-393`), the experiment view
        iterates the raw reverse FK via `experiment.user_permissions`
        (`speleodb/api/v2/views/user_experiment_permission.py:43`). This
        means soft-deleted rows ARE returned. This test pins that as the
        current (pre-existing) contract so any change to the experiment
        view becomes a deliberate, test-driven refactor, not a silent one.
        """
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=self.experiment,
            level=PermissionLevel.READ_ONLY,
        )
        other_with_perm = UserFactory.create(email=_unique_email("other-perm"))
        UserExperimentPermissionFactory.create(
            user=other_with_perm,
            experiment=self.experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Cross-experiment isolation: a perm on a DIFFERENT experiment must
        # NOT leak into this response.
        noise_user = UserFactory.create(email=_unique_email("noise"))
        other_experiment = ExperimentFactory.create(created_by=noise_user.email)
        UserExperimentPermissionFactory.create(
            user=noise_user,
            experiment=other_experiment,
            level=PermissionLevel.READ_ONLY,
        )

        # Soft-deleted perm on THIS experiment. Per the quirk documented in
        # the docstring, this DOES currently appear in the response.
        sd_user = UserFactory.create(email=_unique_email("sd"))
        soft_deleted = UserExperimentPermissionFactory.create(
            user=sd_user,
            experiment=self.experiment,
            level=PermissionLevel.READ_ONLY,
        )
        soft_deleted.deactivate(deactivated_by=self.user)

        response = self.client.get(self.url, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK, response.data

        emails = [perm["user"] for perm in response.data["permissions"]]
        assert self.user.email in emails, emails
        assert other_with_perm.email in emails, emails
        assert noise_user.email not in emails, emails  # cross-experiment isolation
        # Soft-deleted DOES appear (view quirk) — pin it.
        assert sd_user.email in emails, emails
        assert len(response.data["permissions"]) == 3, response.data  # noqa: PLR2004


# =============================================================================
# DETAIL endpoint — CREATE (POST)
# =============================================================================


@pytest.mark.django_db
class TestExperimentUserPermissionCreate(BaseAPITestCase):
    """POST creates or reactivates a permission. Admin-only."""

    def setUp(self) -> None:
        super().setUp()
        self.experiment = ExperimentFactory.create(created_by=self.user.email)
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=self.experiment,
            level=PermissionLevel.ADMIN,
        )
        self.target = UserFactory.create(email=_unique_email("target"))
        self.url = reverse(
            "api:v2:experiment-user-permissions-detail",
            kwargs={"id": self.experiment.id},
        )

    # ---- authz ----

    def test_post_returns_403_for_anonymous(self) -> None:
        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": "READ_ONLY"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_requires_admin_read_and_write_rejected(self) -> None:
        other = UserFactory.create(email=_unique_email("rw-caller"))
        UserExperimentPermissionFactory.create(
            user=other,
            experiment=self.experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )
        token, _ = Token.objects.get_or_create(user=other)
        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": "READ_ONLY"},
            format="json",
            headers={"authorization": f"Token {token.key}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_requires_admin_read_only_rejected(self) -> None:
        other = UserFactory.create(email=_unique_email("ro-caller"))
        UserExperimentPermissionFactory.create(
            user=other,
            experiment=self.experiment,
            level=PermissionLevel.READ_ONLY,
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

    def test_happy_path(self) -> None:
        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": "READ_AND_WRITE"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data["permission"]["user"] == self.target.email, response.data
        assert response.data["permission"]["level"] == "READ_AND_WRITE", response.data

        perm = ExperimentUserPermission.objects.get(
            experiment=self.experiment, user=self.target, is_active=True
        )
        assert perm.level == PermissionLevel.READ_AND_WRITE, perm.level

    # ---- self-target guard ----

    def test_cannot_target_self(self) -> None:
        # `_process_request_data` raises NotAuthorizedError (401). The former
        # in-method 400 branches have been deleted (see
        # speleodb/api/v2/views/user_experiment_permission.py).
        response = self.client.post(
            self.url,
            {"user": self.user.email, "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.data
        assert "own permission" in str(response.data).lower(), response.data

    # ---- validation ----

    def test_rejects_unknown_user(self) -> None:
        response = self.client.post(
            self.url,
            {"user": "nobody@nowhere.test", "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    def test_rejects_inactive_target_user(self) -> None:
        inactive = UserFactory.create(email=_unique_email("inactive"))
        inactive.is_active = False
        inactive.save()
        response = self.client.post(
            self.url,
            {"user": inactive.email, "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.data
        assert "inactive" in str(response.data).lower(), response.data

    def test_rejects_invalid_level(self) -> None:
        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": "BOGUS"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_rejects_web_viewer_level(self) -> None:
        """Experiment perms reject WEB_VIEWER (model uses choices_no_webviewer)."""
        response = self.client.post(
            self.url,
            {"user": self.target.email, "level": "WEB_VIEWER"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_rejects_missing_level(self) -> None:
        # Missing body field now maps to HTTP 400 via `MissingFieldError`.
        response = self.client.post(
            self.url,
            {"user": self.target.email},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "missing" in str(response.data).lower(), response.data

    def test_rejects_missing_user(self) -> None:
        response = self.client.post(
            self.url,
            {"level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "missing" in str(response.data).lower(), response.data

    def test_rejects_empty_body(self) -> None:
        response = self.client.post(
            self.url,
            {},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    # ---- duplicate / reactivation ----

    def test_duplicate_active_fails(self) -> None:
        UserExperimentPermissionFactory.create(
            user=self.target,
            experiment=self.experiment,
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

    def test_reactivates_deactivated_permission(self) -> None:
        perm = UserExperimentPermissionFactory.create(
            user=self.target,
            experiment=self.experiment,
            level=PermissionLevel.READ_ONLY,
        )
        perm.deactivate(deactivated_by=self.user)
        # No second save — deactivate() already persisted.
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
        assert perm.deactivated_by is None, perm.deactivated_by


# =============================================================================
# DETAIL endpoint — UPDATE (PUT)
# =============================================================================


@pytest.mark.django_db
class TestExperimentUserPermissionUpdate(BaseAPITestCase):
    """PUT updates an existing permission."""

    def setUp(self) -> None:
        super().setUp()
        self.experiment = ExperimentFactory.create(created_by=self.user.email)
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=self.experiment,
            level=PermissionLevel.ADMIN,
        )
        self.target = UserFactory.create(email=_unique_email("target-put"))
        self.existing = UserExperimentPermissionFactory.create(
            user=self.target,
            experiment=self.experiment,
            level=PermissionLevel.READ_ONLY,
        )
        self.url = reverse(
            "api:v2:experiment-user-permissions-detail",
            kwargs={"id": self.experiment.id},
        )

    def test_put_returns_403_for_anonymous(self) -> None:
        response = self.client.put(
            self.url,
            {"user": self.target.email, "level": "READ_AND_WRITE"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_requires_admin(self) -> None:
        other = UserFactory.create(email=_unique_email("rw-put"))
        UserExperimentPermissionFactory.create(
            user=other,
            experiment=self.experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )
        token, _ = Token.objects.get_or_create(user=other)
        response = self.client.put(
            self.url,
            {"user": self.target.email, "level": "READ_AND_WRITE"},
            format="json",
            headers={"authorization": f"Token {token.key}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_happy_path(self) -> None:
        response = self.client.put(
            self.url,
            {"user": self.target.email, "level": "READ_AND_WRITE"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        self.existing.refresh_from_db()
        assert self.existing.level == PermissionLevel.READ_AND_WRITE

    def test_cannot_target_self(self) -> None:
        response = self.client.put(
            self.url,
            {"user": self.user.email, "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.data
        assert "own permission" in str(response.data).lower(), response.data

    def test_404_when_no_active_permission(self) -> None:
        stranger = UserFactory.create(email=_unique_email("stranger-put"))
        response = self.client.put(
            self.url,
            {"user": stranger.email, "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    def test_put_404_when_permission_is_soft_deleted(self) -> None:
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


# =============================================================================
# DETAIL endpoint — DELETE
# =============================================================================


@pytest.mark.django_db
class TestExperimentUserPermissionDelete(BaseAPITestCase):
    """DELETE deactivates an existing permission."""

    def setUp(self) -> None:
        super().setUp()
        self.experiment = ExperimentFactory.create(created_by=self.user.email)
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=self.experiment,
            level=PermissionLevel.ADMIN,
        )
        self.target = UserFactory.create(email=_unique_email("target-del"))
        self.existing = UserExperimentPermissionFactory.create(
            user=self.target,
            experiment=self.experiment,
            level=PermissionLevel.READ_ONLY,
        )
        self.url = reverse(
            "api:v2:experiment-user-permissions-detail",
            kwargs={"id": self.experiment.id},
        )

    def test_delete_returns_403_for_anonymous(self) -> None:
        response = self.client.delete(
            self.url,
            {"user": self.target.email},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_requires_admin(self) -> None:
        other = UserFactory.create(email=_unique_email("rw-del"))
        UserExperimentPermissionFactory.create(
            user=other,
            experiment=self.experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )
        token, _ = Token.objects.get_or_create(user=other)
        response = self.client.delete(
            self.url,
            {"user": self.target.email},
            format="json",
            headers={"authorization": f"Token {token.key}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_happy_path(self) -> None:
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

    def test_cannot_target_self(self) -> None:
        response = self.client.delete(
            self.url,
            {"user": self.user.email},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.data
        assert "own permission" in str(response.data).lower(), response.data

    def test_404_when_no_active_permission(self) -> None:
        stranger = UserFactory.create(email=_unique_email("stranger-del"))
        response = self.client.delete(
            self.url,
            {"user": stranger.email},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    def test_delete_is_idempotent_second_call_returns_404(self) -> None:
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


# =============================================================================
# MATRIX: list-endpoint access by experiment permission level
# =============================================================================


@parameterized_class(
    [
        {
            "level": PermissionLevel.READ_ONLY,
            "expected_status": status.HTTP_200_OK,
        },
        {
            "level": PermissionLevel.READ_AND_WRITE,
            "expected_status": status.HTTP_200_OK,
        },
        {
            "level": PermissionLevel.ADMIN,
            "expected_status": status.HTTP_200_OK,
        },
    ]
)
@pytest.mark.django_db
class TestExperimentUserPermissionListMatrix(BaseAPITestCase):
    """List-endpoint access matrix (experiment model has no team perms)."""

    level: PermissionLevel
    expected_status: int

    def test_list_access_matrix(self) -> None:
        experiment = ExperimentFactory.create(created_by=self.user.email)
        UserExperimentPermissionFactory.create(
            user=self.user, experiment=experiment, level=self.level
        )
        response = self.client.get(
            reverse("api:v2:experiment-user-permissions", kwargs={"id": experiment.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == self.expected_status, response.data


@pytest.mark.django_db
class TestExperimentUserPermissionListNoPermission(BaseAPITestCase):
    """Explicit coverage of the "no perm at all" branch (not in matrix)."""

    def test_list_no_perm_returns_403(self) -> None:
        experiment = ExperimentFactory.create(
            created_by=UserFactory.create(email=_unique_email("creator")).email
        )
        response = self.client.get(
            reverse("api:v2:experiment-user-permissions", kwargs={"id": experiment.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data


# =============================================================================
# MATRIX: detail-endpoint POST — admin-only
# =============================================================================


@parameterized_class(
    [
        {
            "level": PermissionLevel.READ_ONLY,
            "expected_status": status.HTTP_403_FORBIDDEN,
        },
        {
            "level": PermissionLevel.READ_AND_WRITE,
            "expected_status": status.HTTP_403_FORBIDDEN,
        },
        {
            "level": PermissionLevel.ADMIN,
            "expected_status": status.HTTP_201_CREATED,
        },
    ]
)
@pytest.mark.django_db
class TestExperimentUserPermissionDetailPostMatrix(BaseAPITestCase):
    """Detail-endpoint POST — only experiment admins can grant perms."""

    level: PermissionLevel
    expected_status: int

    def test_post_access_matrix(self) -> None:
        experiment = ExperimentFactory.create(created_by=self.user.email)
        UserExperimentPermissionFactory.create(
            user=self.user, experiment=experiment, level=self.level
        )
        target = UserFactory.create(email=_unique_email("matrix-target"))
        response = self.client.post(
            reverse(
                "api:v2:experiment-user-permissions-detail",
                kwargs={"id": experiment.id},
            ),
            {"user": target.email, "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == self.expected_status, response.data
