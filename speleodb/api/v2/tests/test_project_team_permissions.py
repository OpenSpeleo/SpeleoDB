# -*- coding: utf-8 -*-

"""Tests for `project-team-permissions` (list) and
`project-team-permissions-detail` (GET/POST/PUT/DELETE).

View lives in `speleodb/api/v2/views/team_project_permission.py`.

Contract notes:
- The detail view authorises on **project** admin access, NOT on team
  leadership. Project admins can grant/revoke permissions for any team they
  choose; being a team member is never required. This is pinned explicitly
  by `test_post_succeeds_for_non_member_of_team`.
- The GET method on the detail view reads the team UUID from the JSON
  request body, not query params. See `test_get_requires_json_body_with_team`.
- Teams cannot hold ADMIN level — `TeamProjectPermission` has a
  `CheckConstraint(level__in=PermissionLevel.values_no_admin)`. The serializer
  has been tightened to use `choices_no_admin`, so a `level=ADMIN` POST is
  rejected at serialization time with HTTP 400, not at the DB layer with 500.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import pytest
from django.urls import reverse
from parameterized.parameterized import parameterized_class
from rest_framework import status
from rest_framework.authtoken.models import Token

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import SurveyTeamFactory
from speleodb.api.v2.tests.factories import TeamProjectPermissionFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import TeamProjectPermission
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from rest_framework.response import Response
    from rest_framework.test import APIClient


def _unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4()}@test.local"


def _generic_json_get(
    client: APIClient, url: str, body: dict[str, Any], auth: str
) -> Response:
    """GET-with-JSON-body helper.

    `APIClient.generic()`'s mypy stub currently infers the wrong return
    type; `cast(Response, ...)` pins the real runtime type so attribute
    access (`.status_code`, `.data`) type-checks correctly. See the
    class docstring for why a GET body is used at all.
    """
    return cast(
        "Response",
        client.generic(
            "GET",
            url,
            data=json.dumps(body),
            content_type="application/json",
            headers={"authorization": auth},
        ),
    )


# =============================================================================
# LIST endpoint
# =============================================================================


@pytest.mark.django_db
class TestProjectTeamPermissionList(BaseAPIProjectTestCase):
    """Any READ access may see the list."""

    def test_list_returns_403_for_anonymous(self) -> None:
        response = self.client.get(
            reverse("api:v2:project-team-permissions", kwargs={"id": self.project.id}),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.content

    def test_list_denied_without_project_permission(self) -> None:
        response = self.client.get(
            reverse("api:v2:project-team-permissions", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_list_success_returns_only_active_team_perms_for_this_project(
        self,
    ) -> None:
        self.set_test_project_permission(
            level=PermissionLevel.READ_ONLY, permission_type=PermissionType.USER
        )
        team = SurveyTeamFactory.create()
        _ = TeamProjectPermissionFactory.create(
            target=team, project=self.project, level=PermissionLevel.READ_AND_WRITE
        )

        # Noise: team perm on another project, and a soft-deleted perm on
        # this project. Neither should appear in the response.
        other_team_other_project = TeamProjectPermissionFactory.create()
        sd_team = SurveyTeamFactory.create()
        soft_deleted = TeamProjectPermissionFactory.create(
            target=sd_team, project=self.project, level=PermissionLevel.READ_ONLY
        )
        soft_deleted.deactivate(deactivated_by=self.user)

        response = self.client.get(
            reverse("api:v2:project-team-permissions", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data["project"]["id"] == str(self.project.id), response.data

        # Coerce the team id to str uniformly — PrimaryKeyRelatedField returns
        # the raw PK (UUID) at `response.data` level; str() is the stable
        # comparison axis.
        returned_team_ids = {str(p["team"]) for p in response.data["permissions"]}
        assert str(team.id) in returned_team_ids, returned_team_ids
        assert str(other_team_other_project.target.id) not in returned_team_ids, (
            returned_team_ids
        )
        assert str(sd_team.id) not in returned_team_ids, returned_team_ids
        assert len(response.data["permissions"]) == 1, response.data


# =============================================================================
# DETAIL endpoint — full CRUD
# =============================================================================


@pytest.mark.django_db
class TestProjectTeamPermissionDetail(BaseAPIProjectTestCase):
    """Full CRUD on the detail endpoint."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN, permission_type=PermissionType.USER
        )
        self.team = SurveyTeamFactory.create()
        # NOTE: no SurveyTeamMembership for self.user is required. The view
        # checks project-admin access only; team leadership is not a
        # precondition. Pinned by
        # `test_post_succeeds_for_non_member_of_team` below.
        self.url = reverse(
            "api:v2:project-team-permissions-detail",
            kwargs={"id": self.project.id},
        )

    # ---- authz ----

    def test_post_returns_403_for_anonymous(self) -> None:
        response = self.client.post(
            self.url,
            {"team": str(self.team.id), "level": "READ_AND_WRITE"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_put_returns_403_for_anonymous(self) -> None:
        response = self.client.put(
            self.url,
            {"team": str(self.team.id), "level": "READ_AND_WRITE"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_delete_returns_403_for_anonymous(self) -> None:
        response = self.client.delete(
            self.url,
            {"team": str(self.team.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_post_requires_admin(self) -> None:
        other = UserFactory.create(email=_unique_email("rw-caller"))
        _ = UserProjectPermissionFactory(
            target=other, project=self.project, level=PermissionLevel.READ_AND_WRITE
        )
        token, _ = Token.objects.get_or_create(user=other)
        response = self.client.post(
            self.url,
            {"team": str(self.team.id), "level": "READ_ONLY"},
            format="json",
            headers={"authorization": f"Token {token.key}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_put_requires_admin(self) -> None:
        other = UserFactory.create(email=_unique_email("rw-put"))
        _ = UserProjectPermissionFactory(
            target=other, project=self.project, level=PermissionLevel.READ_AND_WRITE
        )
        token, _ = Token.objects.get_or_create(user=other)
        response = self.client.put(
            self.url,
            {"team": str(self.team.id), "level": "READ_ONLY"},
            format="json",
            headers={"authorization": f"Token {token.key}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_delete_requires_admin(self) -> None:
        other = UserFactory.create(email=_unique_email("rw-del"))
        _ = UserProjectPermissionFactory(
            target=other, project=self.project, level=PermissionLevel.READ_AND_WRITE
        )
        token, _ = Token.objects.get_or_create(user=other)
        response = self.client.delete(
            self.url,
            {"team": str(self.team.id)},
            format="json",
            headers={"authorization": f"Token {token.key}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    # ---- POST (create) ----

    def test_post_creates_team_permission_with_correct_level(self) -> None:
        response = self.client.post(
            self.url,
            {"team": str(self.team.id), "level": "READ_AND_WRITE"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data

        perm = TeamProjectPermission.objects.get(
            project=self.project, target=self.team, is_active=True
        )
        assert perm.level == PermissionLevel.READ_AND_WRITE, perm.level

    def test_post_succeeds_for_non_member_of_team(self) -> None:
        """Project admin can set a team's permission without being a member."""
        # self.user has no SurveyTeamMembership for self.team — this test
        # proves the view does NOT require team leadership, only project
        # admin.
        response = self.client.post(
            self.url,
            {"team": str(self.team.id), "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data

    def test_post_duplicate_active_fails_with_already_exist_message(self) -> None:
        _ = TeamProjectPermissionFactory.create(
            target=self.team, project=self.project, level=PermissionLevel.READ_ONLY
        )
        response = self.client.post(
            self.url,
            {"team": str(self.team.id), "level": "READ_AND_WRITE"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "already exist" in str(response.data).lower(), response.data

    def test_post_rejects_invalid_level(self) -> None:
        response = self.client.post(
            self.url,
            {"team": str(self.team.id), "level": "BOGUS"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_post_rejects_admin_level(self) -> None:
        """Teams can't hold ADMIN — rejected by serializer, not by DB.

        Prior to the Phase-2 review cleanup, `level=ADMIN` passed the
        serializer (which accepted all `PermissionLevel.choices`) and hit
        the DB `CheckConstraint`, surfacing as an unhandled 500. The
        serializer has been tightened to `choices_no_admin` so this path
        now returns 400.
        """
        response = self.client.post(
            self.url,
            {"team": str(self.team.id), "level": "ADMIN"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "level" in str(response.data).lower(), response.data

    def test_post_rejects_missing_team(self) -> None:
        response = self.client.post(
            self.url,
            {"level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_post_rejects_missing_level(self) -> None:
        response = self.client.post(
            self.url,
            {"team": str(self.team.id)},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_post_rejects_unknown_team(self) -> None:
        response = self.client.post(
            self.url,
            {"team": str(uuid.uuid4()), "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "does not exist" in str(response.data).lower(), response.data

    def test_post_rejects_malformed_uuid(self) -> None:
        response = self.client.post(
            self.url,
            {"team": "not-a-uuid", "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_post_reactivates_deactivated_permission(self) -> None:
        perm = TeamProjectPermissionFactory.create(
            target=self.team, project=self.project, level=PermissionLevel.READ_ONLY
        )
        perm.deactivate(deactivated_by=self.user)
        assert not perm.is_active
        assert perm.deactivated_by == self.user

        response = self.client.post(
            self.url,
            {"team": str(self.team.id), "level": "READ_AND_WRITE"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data

        perm.refresh_from_db()
        assert perm.is_active
        assert perm.level == PermissionLevel.READ_AND_WRITE
        assert perm.deactivated_by is None, perm.deactivated_by

    # ---- GET (detail) — JSON body contract ----

    def test_get_requires_json_body_with_team(self) -> None:
        """GET reads `team` from request body. Empty body -> serializer 400."""
        response = _generic_json_get(self.client, self.url, {}, self.auth)
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_get_returns_team_permission_when_exists(self) -> None:
        _ = TeamProjectPermissionFactory.create(
            target=self.team, project=self.project, level=PermissionLevel.READ_ONLY
        )
        response = _generic_json_get(
            self.client, self.url, {"team": str(self.team.id)}, self.auth
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert "permission" in response.data, response.data
        assert "project" in response.data, response.data
        assert "team" in response.data, response.data
        assert response.data["permission"]["level"] == "READ_ONLY", response.data

    def test_get_404_when_no_permission(self) -> None:
        response = _generic_json_get(
            self.client, self.url, {"team": str(self.team.id)}, self.auth
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    def test_get_rejects_unknown_team(self) -> None:
        response = _generic_json_get(
            self.client, self.url, {"team": str(uuid.uuid4())}, self.auth
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    # ---- PUT ----

    def test_put_updates_level(self) -> None:
        _ = TeamProjectPermissionFactory.create(
            target=self.team, project=self.project, level=PermissionLevel.READ_ONLY
        )
        response = self.client.put(
            self.url,
            {"team": str(self.team.id), "level": "READ_AND_WRITE"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        perm = TeamProjectPermission.objects.get(
            project=self.project, target=self.team, is_active=True
        )
        assert perm.level == PermissionLevel.READ_AND_WRITE

    def test_put_rejects_admin_level(self) -> None:
        _ = TeamProjectPermissionFactory.create(
            target=self.team, project=self.project, level=PermissionLevel.READ_ONLY
        )
        response = self.client.put(
            self.url,
            {"team": str(self.team.id), "level": "ADMIN"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_put_404_when_no_permission(self) -> None:
        response = self.client.put(
            self.url,
            {"team": str(self.team.id), "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    def test_put_rejects_missing_team(self) -> None:
        response = self.client.put(
            self.url,
            {"level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_put_rejects_missing_level(self) -> None:
        response = self.client.put(
            self.url,
            {"team": str(self.team.id)},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    # ---- DELETE ----

    def test_delete_deactivates(self) -> None:
        perm = TeamProjectPermissionFactory.create(
            target=self.team, project=self.project, level=PermissionLevel.READ_ONLY
        )
        response = self.client.delete(
            self.url,
            {"team": str(self.team.id)},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        perm.refresh_from_db()
        assert not perm.is_active
        assert perm.deactivated_by == self.user, perm.deactivated_by

    def test_delete_404_when_no_permission(self) -> None:
        response = self.client.delete(
            self.url,
            {"team": str(self.team.id)},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    def test_delete_is_idempotent_second_call_returns_404(self) -> None:
        _ = TeamProjectPermissionFactory.create(
            target=self.team, project=self.project, level=PermissionLevel.READ_ONLY
        )
        response1 = self.client.delete(
            self.url,
            {"team": str(self.team.id)},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response1.status_code == status.HTTP_200_OK, response1.data

        response2 = self.client.delete(
            self.url,
            {"team": str(self.team.id)},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response2.status_code == status.HTTP_404_NOT_FOUND, response2.data

    def test_delete_rejects_missing_team(self) -> None:
        response = self.client.delete(
            self.url,
            {},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data


# =============================================================================
# MATRIX: list-endpoint access
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
class TestProjectTeamPermissionListMatrix(BaseAPIProjectTestCase):
    """List-endpoint access matrix."""

    level: PermissionLevel
    permission_type: PermissionType
    expected_status: int

    def test_list_access_matrix(self) -> None:
        self.set_test_project_permission(
            level=self.level, permission_type=self.permission_type
        )
        response = self.client.get(
            reverse("api:v2:project-team-permissions", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == self.expected_status, response.data


# =============================================================================
# MATRIX: detail-endpoint POST — admin-only (+ READ_ONLY can GET per view)
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
class TestProjectTeamPermissionDetailPostMatrix(BaseAPIProjectTestCase):
    """Detail-endpoint POST — only project admins can grant team perms."""

    level: PermissionLevel
    permission_type: PermissionType
    expected_status: int

    def test_post_access_matrix(self) -> None:
        self.set_test_project_permission(
            level=self.level, permission_type=self.permission_type
        )
        target_team = SurveyTeamFactory.create()
        response = self.client.post(
            reverse(
                "api:v2:project-team-permissions-detail",
                kwargs={"id": self.project.id},
            ),
            {"team": str(target_team.id), "level": "READ_ONLY"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == self.expected_status, response.data
