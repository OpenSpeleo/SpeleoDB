# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import SimpleTestCase
from django.urls import resolve
from django.urls import reverse
from rest_framework import status


@pytest.mark.parametrize(
    ("name", "path"),
    [
        (
            "well_known:apple-app-site-association",
            ".well-known/apple-app-site-association",
        ),
        ("well_known:assetlinks.json", ".well-known/assetlinks.json"),
        ("well_known:passkey-endpoints", ".well-known/passkey-endpoints"),
    ],
)
def test_well_known_routes(name: str, path: str) -> None:
    assert reverse(name) == f"/{path}"
    assert resolve(f"/{path}").view_name == name


class AppleAppSiteAssociationTests(SimpleTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.url = reverse("well_known:apple-app-site-association")

    def test_returns_200(self) -> None:
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_content_type_is_json(self) -> None:
        response = self.client.get(self.url)
        assert response["Content-Type"] == "application/json"

    def test_body_contains_applinks(self) -> None:
        response = self.client.get(self.url)
        data: dict[str, Any] = json.loads(response.content)
        assert "applinks" in data

    def test_body_contains_webcredentials(self) -> None:
        response = self.client.get(self.url)
        data: dict[str, Any] = json.loads(response.content)
        assert "webcredentials" in data

    def test_applinks_has_details(self) -> None:
        response = self.client.get(self.url)
        data: dict[str, Any] = json.loads(response.content)
        assert "details" in data["applinks"]
        assert isinstance(data["applinks"]["details"], list)
        assert len(data["applinks"]["details"]) > 0

    def test_rejects_post(self) -> None:
        response = self.client.post(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_rejects_put(self) -> None:
        response = self.client.put(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_rejects_delete(self) -> None:
        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class AssetlinksTests(SimpleTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.url = reverse("well_known:assetlinks.json")

    def test_returns_200(self) -> None:
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_content_type_is_json(self) -> None:
        response = self.client.get(self.url)
        assert response["Content-Type"] == "application/json"

    def test_body_is_json_array(self) -> None:
        response = self.client.get(self.url)
        data: list[dict[str, Any]] = json.loads(response.content)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_entry_has_relation_and_target(self) -> None:
        response = self.client.get(self.url)
        data: list[dict[str, Any]] = json.loads(response.content)
        entry = data[0]
        assert "relation" in entry
        assert "target" in entry

    def test_target_has_android_namespace(self) -> None:
        response = self.client.get(self.url)
        data: list[dict[str, Any]] = json.loads(response.content)
        target: dict[str, Any] = data[0]["target"]
        assert target["namespace"] == "android_app"
        assert target["package_name"] == "org.speleodb.app"

    def test_rejects_post(self) -> None:
        response = self.client.post(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_rejects_put(self) -> None:
        response = self.client.put(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_rejects_delete(self) -> None:
        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class PasskeyEndpointsTests(SimpleTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.url = reverse("well_known:passkey-endpoints")

    def test_returns_200(self) -> None:
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_content_type_is_json(self) -> None:
        response = self.client.get(self.url)
        assert response["Content-Type"] == "application/json"

    def test_body_is_valid_json(self) -> None:
        response = self.client.get(self.url)
        data: dict[str, Any] = json.loads(response.content)
        assert isinstance(data, dict)

    def test_body_is_empty_object(self) -> None:
        response = self.client.get(self.url)
        data: dict[str, Any] = json.loads(response.content)
        assert data == {}

    def test_rejects_post(self) -> None:
        response = self.client.post(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_rejects_put(self) -> None:
        response = self.client.put(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_rejects_delete(self) -> None:
        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class ChangePasswordRedirectTests(SimpleTestCase):
    def test_returns_permanent_redirect(self) -> None:
        response = self.client.get("/.well-known/change-password")
        assert response.status_code == status.HTTP_301_MOVED_PERMANENTLY

    def test_redirects_to_password_page(self) -> None:
        response = self.client.get("/.well-known/change-password")
        assert response["Location"] == reverse("private:user_password")
