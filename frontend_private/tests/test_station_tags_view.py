"""Authentication and server bootstrap contract for the station tag editor."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from rest_framework import status

from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client

    from speleodb.users.models import User

pytestmark = pytest.mark.django_db


def test_station_tags_requires_authentication(client: Client) -> None:
    response = client.get(reverse("private:station_tags"))
    assert response.status_code == status.HTTP_302_FOUND
    assert response["Location"].startswith(reverse("account_login"))


def test_station_tags_renders_authenticated_bootstrap(
    client: Client,
) -> None:
    user: User = UserFactory.create()
    client.force_login(user)
    response = client.get(reverse("private:station_tags"))
    assert response.status_code == status.HTTP_200_OK
    assert response.context["user"] == user
    assert b'data-speleodb-controller="station-tags"' in response.content
    assert b"csrfmiddlewaretoken" in response.content
