# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import random
from typing import Any
from uuid import uuid4

from django.test import override_settings
from django.urls import reverse
from django_countries import countries
from faker import Faker
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.testing.api_contract import assert_api_response
from speleodb.users.models import User
from speleodb.utils.test_utils import named_product


class TestUserAPI(BaseAPITestCase):
    def test_password_change_throttle_matches_contract(self) -> None:
        caches = {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": f"password-contract-{uuid4()}",
            }
        }
        with override_settings(CACHES=caches):
            for attempt in range(4):
                response = self.client.put(
                    reverse("api:v2:user-password-update"),
                    {},
                    format="json",
                    headers={"authorization": self.auth},
                )
                expected = (
                    status.HTTP_400_BAD_REQUEST
                    if attempt < 3  # noqa: PLR2004 - Configured three-per-hour quota.
                    else status.HTTP_429_TOO_MANY_REQUESTS
                )
                assert response.status_code == expected, response.content
                assert_api_response(response)
            assert 0 < int(response.headers["Retry-After"]) <= 3600  # noqa: PLR2004
            assert set(response.json()) == {"detail"}

    def test_put_updates_existing_user_and_matches_api_contract(self) -> None:
        user_count = User.objects.count()
        response = self.client.put(
            reverse("api:v2:user-detail"),
            headers={"authorization": self.auth},
            data={
                "email": self.user.email,
                "name": "Updated Profile Name",
                "country": "MX",
                "email_on_projects_updates": False,
                "email_on_speleodb_updates": True,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert_api_response(response)
        self.user.refresh_from_db()
        assert self.user.name == "Updated Profile Name"
        assert self.user.country == "MX"
        assert User.objects.count() == user_count

    def test_get_user_info(self) -> None:
        endpoint = reverse("api:v2:user-detail")

        auth = self.header_prefix + self.token.key
        response = self.client.get(endpoint, headers={"authorization": auth})

        assert response.status_code == status.HTTP_200_OK, response.data

        for key, val in response.data.items():
            assert getattr(self.user, key) == val, (getattr(self.user, key), val)

    def _patch_user_info(self, *, expect_success: bool = True, **kwargs: Any) -> None:
        endpoint = reverse("api:v2:user-detail")

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

            for key, val in response.data.items():
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
        country = random.choice(list(countries))[0]
        self._patch_user_info(country=country)

    def test_nonexisting_country(self) -> None:
        country = "AA"
        self._patch_user_info(expect_success=False, country=country)

    def test_invalid_email(self) -> None:
        email = "tom@domain"
        self._patch_user_info(expect_success=False, email=email)

    @parameterized.expand(
        [
            ("empty", ""),
            ("null", None),
            ("whitespace", " \t\n "),
            ("unicode_whitespace", "\u00a0\u2003"),
            ("empty_markup", "<b></b>"),
            ("script_only", "<script>alert('name')</script>"),
            ("combining_marks", "\u0301\u0302"),
            ("format_characters", "\u200b\u200d"),
        ]
    )
    def test_invalid_name(self, case: str, name: str | None) -> None:
        original_name: str = self.user.name
        auth: str = self.header_prefix + self.token.key
        response = self.client.patch(
            reverse("api:v2:user-detail"),
            headers={"authorization": auth},
            data=json.dumps({"name": name}),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "name" in response.data["errors"]
        self.user.refresh_from_db()
        assert self.user.name == original_name

    def test_patch_user_name_sanitizes_valid_markup(self) -> None:
        auth: str = self.header_prefix + self.token.key
        response = self.client.patch(
            reverse("api:v2:user-detail"),
            headers={"authorization": auth},
            data=json.dumps({"name": "<b>Ada Lovelace</b>"}),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data["name"] == "Ada Lovelace"
        self.user.refresh_from_db()
        assert self.user.name == "Ada Lovelace"

    @parameterized.expand(["email_on_projects_updates", "email_on_speleodb_updates"])
    def test_invalid_preference(self, name: str) -> None:
        self._patch_user_info(expect_success=False, **{name: None})
