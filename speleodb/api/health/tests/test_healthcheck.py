from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.tests.base_testcase import BaseAPITestCase


@pytest.mark.django_db
class TestHealthCheckApiViews(BaseAPITestCase):
    """
    Test suite for GET /api/health endpoints.
    """

    def setUp(self) -> None:
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=None)

    def test_get_health_status(self) -> None:
        response = self.client.get(reverse("api:health:status"))

        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data["data"] is None, response.data

    def test_get_health_details(self) -> None:
        response = self.client.get(reverse("api:health:details"))

        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data["data"] is None, response.data
