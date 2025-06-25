from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.serializers import PluginReleaseSerializer
from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.api.v1.tests.factories import PluginReleaseFactory


@pytest.mark.django_db
class TestPluginReleasesApiView(BaseAPITestCase):
    """
    Test suite for GET /plugin-releases endpoint.
    """

    url_name: str = (
        "api:v1:plugin_releases"  # Make sure this name is defined in your urls.py
    )

    def setUp(self) -> None:
        super().setUp()
        self.client = APIClient()

    def test_get_all_plugin_releases_ordered(self) -> None:
        """
        Should return all plugin releases ordered by creation_date ascending.
        """
        release1 = PluginReleaseFactory(creation_date="2025-01-01T00:00:00Z")
        release2 = PluginReleaseFactory(creation_date="2025-06-01T00:00:00Z")

        response = self.client.get(reverse(self.url_name))

        assert response.status_code == status.HTTP_200_OK, response.data

        expected = PluginReleaseSerializer(
            [release1, release2],  # type: ignore[list-item]
            many=True,
        ).data

        actual = response.data["data"]
        assert actual == expected, {
            "expected": expected,
            "actual": actual,
        }

        actual_dates = [item["creation_date"] for item in actual]
        assert actual_dates == sorted(actual_dates), (
            "Plugin releases are not ordered by creation_date"
        )

    def test_get_no_plugin_releases(self) -> None:
        """
        Should return an empty list if no plugin releases exist.
        """
        response = self.client.get(reverse(self.url_name))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == []

    def test_multiple_plugin_releases(self) -> None:
        """
        Should return all plugin releases when multiple exist.
        """
        releases = PluginReleaseFactory.create_batch(3)

        response = self.client.get(reverse(self.url_name))

        assert response.status_code == status.HTTP_200_OK

        expected = PluginReleaseSerializer(releases, many=True).data
        assert response.data["data"] == expected

    # Optional: test that ordering is strictly by creation_date ascending
    def test_ordering_by_creation_date(self) -> None:
        release_1 = PluginReleaseFactory()
        release_2 = PluginReleaseFactory()
        release_3 = PluginReleaseFactory()

        response = self.client.get(reverse(self.url_name))

        assert response.status_code == status.HTTP_200_OK

        actual_dates = [item["creation_date"] for item in response.data["data"]]
        sorted_dates = sorted(actual_dates)
        assert actual_dates == sorted_dates, (
            "Plugin releases are not sorted ascending by creation_date"
        )

        # Check that the objects correspond correctly
        actual_ids = [item["id"] for item in response.data["data"]]
        expected_order = [release_1.id, release_2.id, release_3.id]  # type: ignore[attr-defined]
        assert actual_ids == expected_order
