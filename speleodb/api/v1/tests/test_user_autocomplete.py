# -*- coding: utf-8 -*-

from __future__ import annotations

import pytest
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.api.v1.views.user import UserAutocompleteView
from speleodb.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestUserAutocomplete(BaseAPITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.url = reverse("api:v1:user-autocomplete")

    def test_requires_authentication(self) -> None:
        client = APIClient()
        response = client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_returns_matching_results_by_email_and_name(self) -> None:
        # Create a few users
        alice = UserFactory.create(email="alice@example.com", name="Alice Alpha")
        bob = UserFactory.create(email="bob@example.com", name="Bob Beta")
        carol = UserFactory.create(email="carol@example.com", name="Carol Gamma")

        # Search by email fragment
        response = self.client.get(
            self.url,
            data={"query": "bob"},
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK

        payload = response.json()
        data = payload["data"]
        assert isinstance(data, list)

        emails = {item["email"] for item in data}
        assert alice.email not in emails
        assert bob.email in emails
        assert carol.email not in emails

        # Search by name fragment
        response = self.client.get(
            self.url,
            data={"query": "Carol"},
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK

        payload = response.json()
        data = payload["data"]
        assert isinstance(data, list)

        names = {item["name"] for item in data}
        assert alice.name not in names
        assert bob.name not in names
        assert carol.name in names

    @parameterized.expand([None, "", "a", "aa"])
    def test_query_min_length_validation(self, query: str | None) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=self.auth)
        data = {"query": query} if query is not None else None
        response = self.client.get(
            self.url,
            data=data,
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_payload = response.json()
        assert error_payload["error"] == "Incorrect query: minimum 3 chars"

    def test_autocomplete_query_user_name(self) -> None:
        """Regression: querying autocomplete should not raise AssertionError
        about missing queryset / get_queryset on UserAutocompleteView."""
        UserFactory.create(email="user_name@example.com", name="user_name")
        response = self.client.get(
            self.url,
            data={"query": "user_name"},
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_limit_is_10_and_order_by_email(self) -> None:
        # Create many users
        for i in range(50):
            _ = UserFactory.create(email=f"user{i:02d}@example.com", name=f"User {i}")

        # Limit should be 10
        response = self.client.get(
            self.url,
            data={"query": "user"},
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert len(data) == UserAutocompleteView.MAXIMUM_RESULTS

        # Ensure ordering by email ascending
        emails = [item["email"] for item in data]
        assert emails == sorted(emails)
