import pytest
from allauth.headless.conftest import AppClient
from allauth.headless.conftest import Client
from django.urls import reverse
from rest_framework import status


def test_swagger_accessible_by_admin(admin_client: Client) -> None:
    url = reverse("api-docs")
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore


@pytest.mark.django_db
def test_swagger_ui_not_accessible_by_normal_user(client: Client | AppClient) -> None:
    url = reverse("api-docs")
    response = client.get(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN, response.data  # type: ignore


def test_api_schema_generated_successfully(admin_client: Client) -> None:
    url = reverse("api-schema")
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore
