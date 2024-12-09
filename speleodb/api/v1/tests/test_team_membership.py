import random

import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.serializers import SurveyTeamMembershipSerializer
from speleodb.api.v1.serializers import SurveyTeamSerializer
from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.api.v1.tests.factories import UserFactory
from speleodb.users.models import SurveyTeamMembership


def is_subset(subset_dict, super_dict):
    return all(item in super_dict.items() for item in subset_dict.items())


class TestTeamMembershipCreation(TestCase):
    """Test creation of `SurveyTeam`."""

    header_prefix = "Token "

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)

        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)
        self.team = SurveyTeamFactory()

    @parameterized.expand(
        [SurveyTeamMembership.Role.LEADER, SurveyTeamMembership.Role.MEMBER]
    )
    def test_create_team_membership(self, role: SurveyTeamMembership.Role):
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        # Must make the user a team leader to create/modify/delete team memberships
        _ = SurveyTeamMembership.objects.create(
            team=self.team, user=self.user, role=SurveyTeamMembership.Role.LEADER
        )

        new_user = UserFactory()

        data = {"user": new_user.email, "role": role.label}

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:team_membership", kwargs={"id": self.team.id}),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED, (
            response.status_code,
            response.data,
        )

        response_data = response.data["data"]

        membership = self.team.get_membership(user=new_user)
        membership_serializer = SurveyTeamMembershipSerializer(membership)

        assert is_subset(
            subset_dict=response_data["membership"],
            super_dict=membership_serializer.data,
        )

        # refresh to update last modified timestamp
        self.team.refresh_from_db()

        team_serializer = SurveyTeamSerializer(self.team, context={"user": self.user})

        assert is_subset(response_data["team"], team_serializer.data), {
            "reserialized": team_serializer.data,
            "response_data": response_data,
        }

    @parameterized.expand(
        [
            (
                # User that doesn't exist
                {
                    "user": f"{random.randint(1, int(1e9))}@speleodb.com",
                    "role": "LEADER",
                },
            ),
            (
                # Role that doesn't exist
                {
                    "user": None,  # autogenerated
                    "role": "SUPERVISOR",
                },
            ),
            (
                # Role is missing
                {"user": None},  # autogenerated
            ),
            (
                # user is missing
                {"role": "LEADER"},
            ),
        ]
    )
    def test_improper_team_creation(self, data: dict):
        # Must make the user a team leader to create/modify/delete team memberships
        _ = SurveyTeamMembership.objects.create(
            team=self.team, user=self.user, role=SurveyTeamMembership.Role.LEADER
        )

        if "user" in data and data["user"] is None:
            data["user"] = UserFactory()

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:team_membership", kwargs={"id": self.team.id}),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @parameterized.expand([SurveyTeamMembership.Role.MEMBER, None])
    def test_create_team_membership_non_authorized(
        self, role: SurveyTeamMembership.Role | None
    ):
        if role is not None:
            _ = SurveyTeamMembership.objects.create(
                team=self.team, user=self.user, role=role
            )

        new_user = UserFactory()

        data = {"user": new_user.email, "role": SurveyTeamMembership.Role.MEMBER.label}

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:team_membership", kwargs={"id": self.team.id}),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, (
            response.status_code,
            response.data,
        )


class TestTeamMembershipUpdate(TestCase):
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

    @parameterized.expand(
        [
            (SurveyTeamMembership.Role.MEMBER, SurveyTeamMembership.Role.LEADER),
            (SurveyTeamMembership.Role.MEMBER, SurveyTeamMembership.Role.MEMBER),
            (SurveyTeamMembership.Role.LEADER, SurveyTeamMembership.Role.MEMBER),
            (SurveyTeamMembership.Role.LEADER, SurveyTeamMembership.Role.LEADER),
        ]
    )
    def test_full_update_team(
        self, old_role: SurveyTeamMembership.Role, new_role: SurveyTeamMembership.Role
    ):
        target_user = UserFactory()
        _ = SurveyTeamMembership.objects.create(
            team=self.team, user=target_user, role=old_role
        )
        data = {"user": target_user.email, "role": new_role.label}

        auth = self.header_prefix + self.token.key
        response = self.client.put(
            reverse("api:v1:team_membership", kwargs={"id": self.team.id}),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK

        response_data = response.data["data"]

        membership = self.team.get_membership(user=target_user)
        membership_serializer = SurveyTeamMembershipSerializer(membership)

        assert is_subset(
            subset_dict=response_data["membership"],
            super_dict=membership_serializer.data,
        )

        # refresh to update last modified timestamp
        self.team.refresh_from_db()

        team_serializer = SurveyTeamSerializer(self.team, context={"user": self.user})

        assert is_subset(response_data["team"], team_serializer.data), {
            "reserialized": team_serializer.data,
            "response_data": response_data,
        }


#     @parameterized.expand(
#         [
#             # Only 1 arg
#             (
#                 {
#                     "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
#                 },
#             ),
#             (
#                 {
#                     "description": "My description",
#                 },
#             ),
#             (
#                 {
#                     "country": "FR",
#                 },
#             ),
#             # Only 2 arg
#             (
#                 {
#                     "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
#                     "description": "My awesome Team",
#                 },
#             ),
#             (
#                 {
#                     "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
#                     "country": "US",
#                 },
#             ),
#             (
#                 {
#                     "description": "My awesome Team",
#                     "country": "US",
#                 },
#             ),
#             # All 3 args
#             (
#                 {
#                     "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
#                     "description": "My awesome Team",
#                     "country": "US",
#                 },
#             ),
#         ]
#     )
#     def test_partial_update_team(self, data):
#         auth = self.header_prefix + self.token.key
#         response = self.client.patch(
#             reverse("api:v1:one_team_apiview", kwargs={"id": self.team.id}),
#             data=data,
#             headers={"authorization": auth},
#         )

#         assert response.status_code == status.HTTP_200_OK

#         assert is_subset(subset_dict=data, super_dict=response.data["data"])


# class TestTeamUpdateErrors(TestCase):
#     header_prefix = "Token "

#     def setUp(self):
#         self.client = APIClient(enforce_csrf_checks=False)

#         self.user = UserFactory()
#         self.token = TokenFactory(user=self.user)
#         self.team = SurveyTeamFactory()

#     @parameterized.expand(["PATCH", "PUT"])
#     def test_update_as_a_non_member(self, method_type):
#         self.base_test(method_type=method_type)

#     @parameterized.expand(["PATCH", "PUT"])
#     def test_update_as_a_member(self, method_type):
#         _ = SurveyTeamMembership.objects.create(
#             team=self.team, user=self.user, role=SurveyTeamMembership.Role.MEMBER
#         )

#         self.base_test(method_type=method_type)

#     def base_test(self, method_type):
#         team_data = {
#             "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
#             "description": "My awesome Team",
#             "country": "US",
#         }

#         auth = self.header_prefix + self.token.key
#         response = getattr(self.client, method_type.lower())(
#             reverse("api:v1:one_team_apiview", kwargs={"id": self.team.id}),
#             data=team_data,
#             headers={"authorization": auth},
#         )

#         assert response.status_code == status.HTTP_403_FORBIDDEN


class TestTeamMembershipDelete(TestCase):
    header_prefix = "Token "

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)

        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)
        self.team = SurveyTeamFactory()

        self.target_user = UserFactory()
        _ = SurveyTeamMembership.objects.create(
            team=self.team, user=self.target_user, role=SurveyTeamMembership.Role.MEMBER
        )

    def test_delete(self):
        # Must make the user a team leader to modify the team
        _ = SurveyTeamMembership.objects.create(
            team=self.team, user=self.user, role=SurveyTeamMembership.Role.LEADER
        )

        auth = self.header_prefix + self.token.key
        response = self.client.delete(
            reverse("api:v1:team_membership", kwargs={"id": self.team.id}),
            data={"user": self.target_user.email},
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK

        with pytest.raises(ObjectDoesNotExist):
            self.team.get_membership(user=self.target_user)

    @parameterized.expand([SurveyTeamMembership.Role.MEMBER, None])
    def test_delete_error(self, role: SurveyTeamMembership.Role | None):
        if role is not None:
            _ = SurveyTeamMembership.objects.create(
                team=self.team, user=self.user, role=role
            )

        auth = self.header_prefix + self.token.key
        response = self.client.delete(
            reverse("api:v1:team_membership", kwargs={"id": self.team.id}),
            data={"user": self.target_user.email},
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestGetTeamMembership(TestCase):
    header_prefix = "Token "

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)

        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)
        self.team = SurveyTeamFactory()

    @parameterized.expand(
        [SurveyTeamMembership.Role.LEADER, SurveyTeamMembership.Role.MEMBER, None]
    )
    def test_get_team_membership(self, role: SurveyTeamMembership.Role | None):
        if role is not None:
            membership = SurveyTeamMembership.objects.create(
                team=self.team, user=self.user, role=role
            )

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse("api:v1:team_membership", kwargs={"id": self.team.id}),
            headers={"authorization": auth},
        )

        if role is None:
            assert (
                response.status_code == status.HTTP_403_FORBIDDEN
            ), response.status_code

        else:
            assert response.status_code == status.HTTP_200_OK, response.status_code

            mbrship_serializer = SurveyTeamMembershipSerializer(membership)

            response_data = response.data["data"]

            assert mbrship_serializer.data == response_data["membership"], {
                "reserialized": mbrship_serializer.data,
                "response_data": response_data,
            }

            team_serializer = SurveyTeamSerializer(
                self.team, context={"user": self.user}
            )

            assert team_serializer.data == response_data["team"], {
                "reserialized": team_serializer.data,
                "response_data": response_data,
            }

    def test_get_membership_non_existing_team(self):
        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse("api:v1:team_membership", kwargs={"id": self.team.id + 1}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.status_code

    @parameterized.expand(
        [SurveyTeamMembership.Role.LEADER, SurveyTeamMembership.Role.MEMBER, None]
    )
    def test_get_all_team_members(self, role: SurveyTeamMembership.Role | None):
        N_MEMBERS = 10  # noqa: N806

        if role is not None:
            _ = SurveyTeamMembership.objects.create(
                team=self.team, user=self.user, role=role
            )

        for _ in range(N_MEMBERS):
            user = UserFactory()
            _ = SurveyTeamMembership.objects.create(
                team=self.team, user=user, role=SurveyTeamMembership.Role.MEMBER
            )

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse("api:v1:team_list_membership", kwargs={"id": self.team.id}),
            headers={"authorization": auth},
        )

        if role is None:
            assert (
                response.status_code == status.HTTP_403_FORBIDDEN
            ), response.status_code

        else:
            assert response.status_code == status.HTTP_200_OK, response.status_code

            response_data = response.data["data"]

            # Includes the requester => `+ 1`
            assert len(response_data["memberships"]) == N_MEMBERS + 1

            serializer = SurveyTeamSerializer(self.team, context={"user": self.user})

            assert serializer.data == response_data["team"], {
                "reserialized": serializer.data,
                "response_data": response_data["team"],
            }

    def test_get_all_memberships_non_existing_team(self):
        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse("api:v1:team_list_membership", kwargs={"id": self.team.id + 1}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.status_code
