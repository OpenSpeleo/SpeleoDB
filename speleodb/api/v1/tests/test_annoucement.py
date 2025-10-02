from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.serializers import PublicAnnoucementSerializer
from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.api.v1.tests.factories import PublicAnnoucementFactory


@pytest.mark.django_db
class TestPublicAnnouncementApiView(BaseAPITestCase):
    """
    Test suite for GET /public-announcements endpoint.
    """

    url_name: str = (
        "api:v1:public-announcements"  # Ensure you have this named in your urls.py
    )

    def setUp(self) -> None:
        super().setUp()
        self.client = APIClient()

    def test_get_active_announcements(self) -> None:
        """
        Should return only active announcements ordered by creation_date.
        """
        announcement1 = PublicAnnoucementFactory(title="Announcement 1", is_active=True)
        announcement2 = PublicAnnoucementFactory(title="Announcement 2", is_active=True)
        _ = PublicAnnoucementFactory(title="Inactive Announcement", is_active=False)

        response = self.client.get(reverse(self.url_name))

        assert response.status_code == status.HTTP_200_OK, response.data

        expected = PublicAnnoucementSerializer(
            [announcement1, announcement2],  # type: ignore[list-item]
            many=True,
        ).data

        actual = response.data["data"]
        assert actual == expected, {
            "expected": expected,
            "actual": actual,
        }

    def test_get_no_announcements(self) -> None:
        """
        Should return an empty list if no active announcements exist.
        """
        _ = PublicAnnoucementFactory(is_active=False)

        response = self.client.get(reverse(self.url_name))

        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data["data"] == []

    def test_get_announcements_ordering(self) -> None:
        """
        Should order announcements by creation_date ascending.
        """
        announcement1 = PublicAnnoucementFactory(creation_date="2025-01-01T00:00:00Z")
        announcement2 = PublicAnnoucementFactory(creation_date="2025-06-01T00:00:00Z")

        response = self.client.get(reverse(self.url_name))

        assert response.status_code == status.HTTP_200_OK
        actual_titles = [ann["title"] for ann in response.data["data"]]
        assert actual_titles == [announcement1.title, announcement2.title], (  # pyright: ignore[reportAttributeAccessIssue]
            actual_titles
        )

    def test_get_all_announcements_with_inactive_filtered_out(self) -> None:
        """
        Should filter out inactive announcements even if others exist.
        """
        _ = PublicAnnoucementFactory(is_active=False)
        active_announcement = PublicAnnoucementFactory(is_active=True)

        response = self.client.get(reverse(self.url_name))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 1
        assert response.data["data"][0]["title"] == active_announcement.title  # pyright: ignore[reportAttributeAccessIssue]
