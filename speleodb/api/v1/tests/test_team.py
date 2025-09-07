# -*- coding: utf-8 -*-

from __future__ import annotations

import random
import uuid

from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.serializers import SurveyTeamSerializer
from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.api.v1.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v1.tests.utils import is_subset
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembershipRole


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
            reverse("api:v1:teams"),
            data=team_data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED, (
            response.status_code,
            response.data,
        )

        assert is_subset(subset_dict=team_data, super_dict=response.data["data"])

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
            reverse("api:v1:teams"),
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
            reverse("api:v1:team-detail", kwargs={"id": self.team.id}),
            data=team_data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK, response.data

        assert is_subset(subset_dict=team_data, super_dict=response.data["data"])

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
            reverse("api:v1:team-detail", kwargs={"id": self.team.id}),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK, response.data

        assert is_subset(subset_dict=data, super_dict=response.data["data"])


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
            reverse("api:v1:team-detail", kwargs={"id": self.team.id}),
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
        # Must make the user a team leader to modify the team
        _ = SurveyTeamMembershipFactory(
            team=self.team, user=self.user, role=SurveyTeamMembershipRole.LEADER
        )

        auth = self.header_prefix + self.token.key
        response = self.client.delete(
            reverse("api:v1:team-detail", kwargs={"id": self.team.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT, response.data

    @parameterized.expand([SurveyTeamMembershipRole.MEMBER, None])
    def test_delete_error(self, role: SurveyTeamMembershipRole | None) -> None:
        if role is not None:
            _ = SurveyTeamMembershipFactory(team=self.team, user=self.user, role=role)

        auth = self.header_prefix + self.token.key
        response = self.client.delete(
            reverse("api:v1:team-detail", kwargs={"id": self.team.id}),
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
            reverse("api:v1:team-detail", kwargs={"id": self.team.id}),
            headers={"authorization": auth},
        )

        if role is None:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

        else:
            assert response.status_code == status.HTTP_200_OK, response.status_code

            serializer = SurveyTeamSerializer(self.team, context={"user": self.user})

            assert serializer.data == response.data["data"], {
                "reserialized": serializer.data,
                "response_data": response.data["data"],
            }

    def test_get_non_existing_team(self) -> None:
        auth = self.header_prefix + self.token.key
        # Use a random UUID that doesn't exist
        non_existing_id = uuid.uuid4()
        response = self.client.get(
            reverse("api:v1:team-detail", kwargs={"id": non_existing_id}),
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
            reverse("api:v1:teams"),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK, response.status_code

        if role is None:
            assert len(response.data["data"]) == 0

        else:
            assert len(response.data["data"]) == 1

            serializer = SurveyTeamSerializer(self.team, context={"user": self.user})

            assert serializer.data == response.data["data"][0], {
                "reserialized": serializer.data,
                "response_data": response.data["data"],
            }
