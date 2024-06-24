import json
import random

from django.test import TestCase
from django.urls import reverse
from django_countries import countries
from faker import Faker
from parameterized import parameterized
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.api.v1.tests.factories import UserFactory
from speleodb.utils.test_utils import named_product


class TestUserAPI(TestCase):
    header_prefix = "Token "

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)

    def test_get_user_info(self):
        endpoint = reverse("api:v1_users:user_info")

        auth = self.header_prefix + self.token.key
        response = self.client.get(endpoint, headers={"authorization": auth})

        assert response.status_code == status.HTTP_200_OK, response.status_code

        target = {
            "success": True,
            "url": f"http://testserver{endpoint}",
        }

        for key, val in target.items():
            assert val == response.data[key], response.data

        for key, val in response.data["data"].items():
            assert getattr(self.user, key) == val, (getattr(self.user, key), val)

    @parameterized.expand(
        named_product(
            email_on_projects_updates=[True, False],
            email_on_speleodb_updates=[True, False],
        )
    )
    def test_patch_user_preference(
        self, email_on_projects_updates, email_on_speleodb_updates
    ):
        self._patch_user_info(
            email_on_projects_updates=email_on_projects_updates,
            email_on_speleodb_updates=email_on_speleodb_updates,
        )

    def test_patch_user_name(self):
        name = Faker().name()
        self._patch_user_info(name=name)

    def test_patch_country(self):
        country = random.choice(countries)[0]
        self._patch_user_info(country=country)

    def test_nonexisting_country(self):
        country = "AA"
        self._patch_user_info(country=country, expect_success=False)

    def test_invalid_email(self):
        email = "tom@domain"
        self._patch_user_info(email=email, expect_success=False)

    def test_invalid_name(self):
        name = ""
        self._patch_user_info(name=name, expect_success=False)

    @parameterized.expand(["email_on_projects_updates", "email_on_speleodb_updates"])
    def test_invalid_preference(self, name):
        self._patch_user_info(expect_success=False, **{name: None})

    def _patch_user_info(self, expect_success=True, **kwargs):
        endpoint = reverse("api:v1_users:user_info")

        auth = self.header_prefix + self.token.key
        response = self.client.patch(
            endpoint,
            headers={"authorization": auth},
            data=json.dumps(kwargs),
            content_type="application/json",
        )

        if expect_success:
            assert response.status_code == status.HTTP_200_OK, (
                response.status_code,
                response.data,
            )

            target = {
                "success": True,
                "url": f"http://testserver{endpoint}",
            }

            for key, val in target.items():
                assert val == response.data[key], response.data

            for key, val in response.data["data"].items():
                target = kwargs.get(key, getattr(self.user, key))
                assert target == val, (target, val)

        else:
            assert (
                response.status_code == status.HTTP_400_BAD_REQUEST
            ), response.status_code

        return response.data
