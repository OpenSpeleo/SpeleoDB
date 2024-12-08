import random

from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.api.v1.tests.factories import UserFactory
from speleodb.users.models import SurveyTeamMembership


def is_subset(subset_dict, super_dict):
    return all(item in super_dict.items() for item in subset_dict.items())


class TestTeamCreation(TestCase):
    """Test creation of `SurveyTeam`."""

    header_prefix = "Token "

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)

        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)

    def test_create_team(self):
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
            reverse("api:v1:create_team"),
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
    def test_improper_team_creation(self, kwargs):
        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:create_team"),
            data=kwargs,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestTeamUpdate(TestCase):
    header_prefix = "Token "

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)

        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)
        self.team = SurveyTeamFactory()

        # Must make the user a team leader to modify the team
        _ = SurveyTeamMembership.objects.create(
            team=self.team, user=self.user, role=SurveyTeamMembership.Role.LEADER
        )

    def test_full_update_team(self):
        team_data = {
            "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
            "description": "My awesome Team",
            "country": "US",
        }

        auth = self.header_prefix + self.token.key
        response = self.client.put(
            reverse("api:v1:one_team_apiview", kwargs={"id": self.team.id}),
            data=team_data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK

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
    def test_partial_update_team(self, data):
        auth = self.header_prefix + self.token.key
        response = self.client.patch(
            reverse("api:v1:one_team_apiview", kwargs={"id": self.team.id}),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK

        assert is_subset(subset_dict=data, super_dict=response.data["data"])


class TestTeamUpdateErrors(TestCase):
    header_prefix = "Token "

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)

        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)
        self.team = SurveyTeamFactory()

    @parameterized.expand(["PATCH", "PUT"])
    def test_update_as_a_non_member(self, method_type):
        self.base_test(method_type=method_type)

    @parameterized.expand(["PATCH", "PUT"])
    def test_update_as_a_member(self, method_type):
        _ = SurveyTeamMembership.objects.create(
            team=self.team, user=self.user, role=SurveyTeamMembership.Role.MEMBER
        )

        self.base_test(method_type=method_type)

    def base_test(self, method_type):
        team_data = {
            "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
            "description": "My awesome Team",
            "country": "US",
        }

        auth = self.header_prefix + self.token.key
        response = getattr(self.client, method_type.lower())(
            reverse("api:v1:one_team_apiview", kwargs={"id": self.team.id}),
            data=team_data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestTeamDelete(TestCase):
    header_prefix = "Token "

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)

        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)
        self.team = SurveyTeamFactory()

    def test_delete(self):
        # Must make the user a team leader to modify the team
        _ = SurveyTeamMembership.objects.create(
            team=self.team, user=self.user, role=SurveyTeamMembership.Role.LEADER
        )

        auth = self.header_prefix + self.token.key
        response = self.client.delete(
            reverse("api:v1:one_team_apiview", kwargs={"id": self.team.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK

    @parameterized.expand([True, False])
    def test_delete_error(self, is_member: bool):  # noqa: FBT001
        if is_member:
            _ = SurveyTeamMembership.objects.create(
                team=self.team, user=self.user, role=SurveyTeamMembership.Role.MEMBER
            )

        auth = self.header_prefix + self.token.key
        response = self.client.delete(
            reverse("api:v1:one_team_apiview", kwargs={"id": self.team.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN