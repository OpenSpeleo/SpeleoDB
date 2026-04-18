# -*- coding: utf-8 -*-

from __future__ import annotations

import random
import uuid

from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v2.serializers import SurveyTeamSerializer
from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import SurveyTeamFactory
from speleodb.api.v2.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v2.tests.factories import TeamProjectPermissionFactory
from speleodb.api.v2.tests.utils import is_subset
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import SurveyTeamMembershipRole
from speleodb.surveys.models import TeamProjectPermission
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership


class TestTeamCreation(BaseAPITestCase):
    def test_create_team(self) -> None:
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        team_data = {
            "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
            "description": "My awesome Team",
            "country": "US",
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v2:teams"),
            data=team_data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED, (
            response.status_code,
            response.data,
        )

        assert is_subset(subset_dict=team_data, super_dict=response.data)

    @parameterized.expand(
        [
            # With `name` missing
            (
                {
                    "name": "",
                    "description": "My description",
                    "country": "MX",
                },
            ),
            (
                {
                    "description": "My description",
                    "country": "MX",
                },
            ),
            # With `description` missing
            (
                {
                    "name": "Survey Team",
                    "description": "",
                    "country": "MX",
                },
            ),
            (
                {
                    "name": "Into the Jungle",
                    "country": "FR",
                },
            ),
            # With `country` missing
            (
                {
                    "name": "Survey Team",
                    "description": "My survey team",
                    "country": "",
                },
            ),
            (
                {
                    "name": "Survey Team",
                    "description": "My survey team",
                },
            ),
            # With `country` non-existing
            (
                {
                    "name": "Survey Team",
                    "description": "My survey team",
                    "country": "ABC",
                },
            ),
        ]
    )
    def test_improper_team_creation(self, data: dict[str, str]) -> None:
        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v2:teams"),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data


class TestTeamUpdate(BaseAPITestCase):
    team: SurveyTeam

    def setUp(self) -> None:
        super().setUp()
        self.team = SurveyTeamFactory.create()

        # Must make the user a team leader to modify the team
        _ = SurveyTeamMembershipFactory(
            team=self.team, user=self.user, role=SurveyTeamMembershipRole.LEADER
        )

    def test_full_update_team(self) -> None:
        team_data = {
            "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
            "description": "My awesome Team",
            "country": "US",
        }

        auth = self.header_prefix + self.token.key
        response = self.client.put(
            reverse("api:v2:team-detail", kwargs={"id": self.team.id}),
            data=team_data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK, response.data

        assert is_subset(subset_dict=team_data, super_dict=response.data)

    @parameterized.expand(
        [
            # Only 1 arg
            (
                {
                    "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
                },
            ),
            (
                {
                    "description": "My description",
                },
            ),
            (
                {
                    "country": "FR",
                },
            ),
            # Only 2 arg
            (
                {
                    "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
                    "description": "My awesome Team",
                },
            ),
            (
                {
                    "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
                    "country": "US",
                },
            ),
            (
                {
                    "description": "My awesome Team",
                    "country": "US",
                },
            ),
            # All 3 args
            (
                {
                    "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
                    "description": "My awesome Team",
                    "country": "US",
                },
            ),
        ]
    )
    def test_partial_update_team(self, data: dict[str, str]) -> None:
        auth = self.header_prefix + self.token.key
        response = self.client.patch(
            reverse("api:v2:team-detail", kwargs={"id": self.team.id}),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK, response.data

        assert is_subset(subset_dict=data, super_dict=response.data)


class TestTeamUpdateErrors(BaseAPITestCase):
    team: SurveyTeam

    def setUp(self) -> None:
        super().setUp()
        self.team = SurveyTeamFactory.create()

    @parameterized.expand(["PATCH", "PUT"])
    def test_update_as_a_non_member(self, method_type: str) -> None:
        self.base_test(method_type=method_type)

    @parameterized.expand(["PATCH", "PUT"])
    def test_update_as_a_member(self, method_type: str) -> None:
        _ = SurveyTeamMembershipFactory(
            team=self.team, user=self.user, role=SurveyTeamMembershipRole.MEMBER
        )

        self.base_test(method_type=method_type)

    def base_test(self, method_type: str) -> None:
        team_data = {
            "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
            "description": "My awesome Team",
            "country": "US",
        }

        auth = self.header_prefix + self.token.key
        response = getattr(self.client, method_type.lower())(
            reverse("api:v2:team-detail", kwargs={"id": self.team.id}),
            data=team_data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data


class TestTeamDelete(BaseAPITestCase):
    team: SurveyTeam

    def setUp(self) -> None:
        super().setUp()
        self.team = SurveyTeamFactory.create()

    def test_delete(self) -> None:
        """Team DELETE is a soft-delete: the team row stays, memberships
        and team project permissions are deactivated.

        Mirrors `ProjectSpecificApiView.delete` — no hard-delete of the
        top-level entity. See `speleodb/api/v2/views/team.py::delete`.
        """
        # Must make the user a team leader to modify the team.
        _ = SurveyTeamMembershipFactory.create(
            team=self.team, user=self.user, role=SurveyTeamMembershipRole.LEADER
        )
        # One extra active member so we prove the deactivation fan-out.
        extra_member = SurveyTeamMembershipFactory.create(
            team=self.team, role=SurveyTeamMembershipRole.MEMBER
        )
        # Two active team project permissions so the perm-deactivation
        # loop has something to do.
        project_a = ProjectFactory.create(created_by=self.user.email)
        project_b = ProjectFactory.create(created_by=self.user.email)
        perm_a = TeamProjectPermissionFactory.create(
            target=self.team,
            project=project_a,
            level=PermissionLevel.READ_ONLY,
        )
        perm_b = TeamProjectPermissionFactory.create(
            target=self.team,
            project=project_b,
            level=PermissionLevel.READ_AND_WRITE,
        )

        auth = self.header_prefix + self.token.key
        response = self.client.delete(
            reverse("api:v2:team-detail", kwargs={"id": self.team.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK, response.data

        # Team row still exists — not hard-deleted.
        assert SurveyTeam.objects.filter(id=self.team.id).exists()

        # All memberships deactivated.
        active_memberships = SurveyTeamMembership.objects.filter(
            team=self.team, is_active=True
        )
        assert active_memberships.count() == 0, list(active_memberships)
        # Rows still exist (just inactive) — membership history preserved.
        assert SurveyTeamMembership.objects.filter(team=self.team).count() == 2  # noqa: PLR2004

        # Memberships track who deactivated them (audit trail).
        for membership_id in [
            extra_member.id,
        ]:
            membership = SurveyTeamMembership.objects.get(id=membership_id)
            assert not membership.is_active
            assert membership.deactivated_by == self.user

        # All team project permissions deactivated.
        active_perms = TeamProjectPermission.objects.filter(
            target=self.team, is_active=True
        )
        assert active_perms.count() == 0, list(active_perms)
        # Rows preserved.
        assert (
            TeamProjectPermission.objects.filter(target=self.team).count() == 2  # noqa: PLR2004
        )

        # Audit trail on the perms too.
        perm_a.refresh_from_db()
        perm_b.refresh_from_db()
        assert not perm_a.is_active
        assert perm_a.deactivated_by == self.user
        assert not perm_b.is_active
        assert perm_b.deactivated_by == self.user

        # Post-soft-delete, the caller can no longer see the team —
        # `UserHasMemberAccess` rejects the request because there's no
        # active membership.
        response_after = self.client.get(
            reverse("api:v2:team-detail", kwargs={"id": self.team.id}),
            headers={"authorization": auth},
        )
        assert response_after.status_code == status.HTTP_403_FORBIDDEN, (
            response_after.data
        )

    @parameterized.expand([SurveyTeamMembershipRole.MEMBER, None])
    def test_delete_error(self, role: SurveyTeamMembershipRole | None) -> None:
        if role is not None:
            _ = SurveyTeamMembershipFactory(team=self.team, user=self.user, role=role)

        auth = self.header_prefix + self.token.key
        response = self.client.delete(
            reverse("api:v2:team-detail", kwargs={"id": self.team.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data


class TestGetTeam(BaseAPITestCase):
    team: SurveyTeam

    def setUp(self) -> None:
        super().setUp()
        self.team = SurveyTeamFactory.create()

    @parameterized.expand(
        [SurveyTeamMembershipRole.LEADER, SurveyTeamMembershipRole.MEMBER, None]
    )
    def test_get_team(self, role: SurveyTeamMembershipRole | None) -> None:
        if role is not None:
            _ = SurveyTeamMembershipFactory(team=self.team, user=self.user, role=role)

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse("api:v2:team-detail", kwargs={"id": self.team.id}),
            headers={"authorization": auth},
        )

        if role is None:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

        else:
            assert response.status_code == status.HTTP_200_OK, response.status_code

            serializer = SurveyTeamSerializer(self.team, context={"user": self.user})

            assert serializer.data == response.data, {
                "reserialized": serializer.data,
                "response_data": response.data,
            }

    def test_get_non_existing_team(self) -> None:
        auth = self.header_prefix + self.token.key
        # Use a random UUID that doesn't exist
        non_existing_id = uuid.uuid4()
        response = self.client.get(
            reverse("api:v2:team-detail", kwargs={"id": non_existing_id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.status_code

    @parameterized.expand(
        [SurveyTeamMembershipRole.LEADER, SurveyTeamMembershipRole.MEMBER, None]
    )
    def test_get_all_user_team(self, role: SurveyTeamMembershipRole | None) -> None:
        if role is not None:
            _ = SurveyTeamMembershipFactory(team=self.team, user=self.user, role=role)

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse("api:v2:teams"),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK, response.status_code

        if role is None:
            assert len(response.data) == 0

        else:
            assert len(response.data) == 1

            serializer = SurveyTeamSerializer(self.team, context={"user": self.user})

            assert serializer.data == response.data[0], {
                "reserialized": serializer.data,
                "response_data": response.data,
            }
