# import random

# from django.test import TestCase
# from django.urls import reverse
# from parameterized import parameterized
# from rest_framework import status
# from rest_framework.test import APIClient

# from speleodb.api.v1.tests.factories import SurveyTeamFactory
# from speleodb.api.v1.tests.factories import TokenFactory
# from speleodb.api.v1.tests.factories import UserFactory
# from speleodb.users.models import SurveyTeamMembership


# def is_subset(subset_dict, super_dict):
#     return all(item in super_dict.items() for item in subset_dict.items())


# class TestTeamCreation(TestCase):
#     """Test creation of `SurveyTeam`."""

#     header_prefix = "Token "

#     def setUp(self):
#         self.client = APIClient(enforce_csrf_checks=False)

#         self.user = UserFactory()
#         self.token = TokenFactory(user=self.user)

#     def test_create_team(self):
#         """
#         Ensure POSTing json over token auth with correct
#         credentials passes and does not require CSRF
#         """

#         team_data = {
#             "name": f"My Super Awesome {random.randint(1, int(1e9))} Team",
#             "description": "My awesome Team",
#             "country": "US",
#         }

#         auth = self.header_prefix + self.token.key
#         response = self.client.post(
#             reverse("api:v1:create_team"),
#             data=team_data,
#             headers={"authorization": auth},
#         )

#         assert response.status_code == status.HTTP_201_CREATED, (
#             response.status_code,
#             response.data,
#         )

#         assert is_subset(subset_dict=team_data, super_dict=response.data["data"])
