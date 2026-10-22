# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.urls import resolve
from django.urls import reverse
from rest_framework import status

if TYPE_CHECKING:
    from django.test import Client


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


def test_apple_app_association_contract(client: Client) -> None:
    response = client.get(reverse("well_known:apple-app-site-association"))
    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"] == "application/json"
    data = response.json()
    assert data["webcredentials"]["apps"] == ["UDUF7J66TN.org.speleodb.app"]
    assert data["applinks"]["details"][0]["appIDs"] == ["UDUF7J66TN.org.speleodb.app"]
    assert {entry["/"] for entry in data["applinks"]["details"][0]["components"]} == {
        "/app",
        "/app/*",
    }


def test_android_asset_links_contract(client: Client) -> None:
    response = client.get(reverse("well_known:assetlinks.json"))
    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"] == "application/json"
    (entry,) = response.json()
    assert set(entry["relation"]) == {
        "delegate_permission/common.get_login_creds",
        "delegate_permission/common.handle_all_urls",
    }
    target = entry["target"]
    assert target["namespace"] == "android_app"
    assert target["package_name"] == "org.speleodb.app"
    assert target["sha256_cert_fingerprints"] == [
        "ED:5B:2F:D2:A5:F4:C3:FE:95:51:5C:B0:70:2E:1E:18:69:C5:76:C7:59:EE:31:CE:60:5C:2D:B0:1E:BC:D0:70"
    ]


def test_passkey_discovery_reports_unsupported(client: Client) -> None:
    response = client.get(reverse("well_known:passkey-endpoints"))
    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"] == "application/json"
    assert response.json() == {}


@pytest.mark.parametrize(
    "name",
    [
        "well_known:apple-app-site-association",
        "well_known:assetlinks.json",
        "well_known:passkey-endpoints",
    ],
)
def test_discovery_endpoints_are_read_only(client: Client, name: str) -> None:
    response = client.post(reverse(name))
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_change_password_redirects_permanently(client: Client) -> None:
    response = client.get("/.well-known/change-password")
    assert response.status_code == status.HTTP_301_MOVED_PERMANENTLY
    assert response["Location"] == reverse("private:user_password")
