# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import random
from typing import Any

from django.urls import reverse
from django_countries import countries
from faker import Faker
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.utils.test_utils import named_product


class TestUserAPI(BaseAPITestCase):
    def test_get_user_info(self) -> None:
        endpoint = reverse("api:v1:user_info")

        auth = self.header_prefix + self.token.key
        response = self.client.get(endpoint, headers={"authorization": auth})

        assert response.status_code == status.HTTP_200_OK, response.data

        target = {
            "success": True,
            "url": f"http://testserver{endpoint}",
        }

        for key, val in target.items():
            assert val == response.data[key], response.data

        for key, val in response.data["data"].items():
            assert getattr(self.user, key) == val, (getattr(self.user, key), val)

    def _patch_user_info(self, *, expect_success: bool = True, **kwargs: Any) -> None:
        endpoint = reverse("api:v1:user_info")

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
            assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    @parameterized.expand(
        named_product(
            email_on_projects_updates=[True, False],
            email_on_speleodb_updates=[True, False],
        )
    )
    def test_patch_user_preference(
        self, email_on_projects_updates: bool, email_on_speleodb_updates: bool
    ) -> None:
        self._patch_user_info(
            email_on_projects_updates=email_on_projects_updates,
            email_on_speleodb_updates=email_on_speleodb_updates,
        )

    def test_patch_user_name(self) -> None:
        name = Faker().name()
        self._patch_user_info(name=name)

    def test_patch_country(self) -> None:
        country = random.choice(countries)[0]
        self._patch_user_info(country=country)

    def test_nonexisting_country(self) -> None:
        country = "AA"
        self._patch_user_info(expect_success=False, country=country)

    def test_invalid_email(self) -> None:
        email = "tom@domain"
        self._patch_user_info(expect_success=False, email=email)

    def test_invalid_name(self) -> None:
        name = ""
        self._patch_user_info(expect_success=False, name=name)

    @parameterized.expand(["email_on_projects_updates", "email_on_speleodb_updates"])
    def test_invalid_preference(self, name: str) -> None:
        self._patch_user_info(expect_success=False, **{name: None})
