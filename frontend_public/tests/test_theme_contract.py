from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any

from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from speleodb.gis.models import GISView
from speleodb.users.tests.factories import UserFactory


class DarkDocumentThemeContractTests(TestCase):
    app_stylesheet: str = "speleodb/vite/assets/style-app"

    def assert_dark_document(
        self,
        html: str,
        *,
        expects_dark_class: bool,
        expects_app_stylesheet: bool = True,
    ) -> None:
        color_scheme_position: int = html.index(
            '<meta name="color-scheme" content="dark">'
        )
        darkreader_lock_position: int = html.index('<meta name="darkreader-lock">')
        first_stylesheet_position: int = html.index('rel="stylesheet"')

        assert color_scheme_position < first_stylesheet_position
        assert darkreader_lock_position < first_stylesheet_position

        html_element: re.Match[str] | None = re.search(r"<html\b[^>]*>", html)
        assert html_element is not None
        class_attribute: re.Match[str] | None = re.search(
            r'\bclass="([^"]*)"', html_element.group(0)
        )
        classes: set[str] = (
            set(class_attribute.group(1).split())
            if class_attribute is not None
            else set()
        )
        assert ("dark" in classes) is expects_dark_class

        expected_count: int = 1 if expects_app_stylesheet else 0
        assert html.count(self.app_stylesheet) == expected_count

    def test_public_root_declares_dark_without_private_variant(self) -> None:
        response: Any = self.client.get(reverse("home"))
        assert response.status_code == HTTPStatus.OK
        self.assert_dark_document(
            response.content.decode(),
            expects_dark_class=False,
        )
        html: str = response.content.decode()
        assert html.index("fonts.googleapis.com/css2?family=Inter:wght@800") < (
            html.index(self.app_stylesheet)
        )
        assert html.index(self.app_stylesheet) < html.index("style-public-shell")

    def test_private_document_keeps_class_controlled_dark_variant(self) -> None:
        user = UserFactory.create()
        self.client.force_login(user)

        response: Any = self.client.get(reverse("private:user_dashboard"))
        assert response.status_code == HTTPStatus.OK
        self.assert_dark_document(
            response.content.decode(),
            expects_dark_class=True,
        )

    def test_ariane_webview_declares_dark_without_a_variant_class(self) -> None:
        response: Any = self.client.get(reverse("webview_ariane"))
        assert response.status_code == HTTPStatus.OK
        self.assert_dark_document(
            response.content.decode(),
            expects_dark_class=False,
        )

    def test_public_gis_loads_the_unified_asset_once_in_cascade_order(self) -> None:
        owner = UserFactory.create()
        gis_view = GISView.objects.create(
            name="Theme contract",
            owner=owner,
            allow_precise_zoom=False,
        )

        response: Any = self.client.get(
            reverse("gis_view_map", kwargs={"gis_token": gis_view.gis_token})
        )
        assert response.status_code == HTTPStatus.OK
        html: str = response.content.decode()
        self.assert_dark_document(html, expects_dark_class=False)

        stylesheet_markers: tuple[str, ...] = (
            self.app_stylesheet,
            "style-public-shell",
            "style-private-shell",
            "style-shared-modal",
            "style-map-viewer",
            "api.mapbox.com/mapbox-gl-js/v3.12.0/mapbox-gl.css",
        )
        positions: list[int] = [html.index(marker) for marker in stylesheet_markers]
        assert positions == sorted(positions)
        assert "private/css/style.css" not in html

    def test_error_document_declares_dark_without_a_variant_class(self) -> None:
        html: str = render_to_string("base_error.html")
        self.assert_dark_document(
            html,
            expects_dark_class=False,
            expects_app_stylesheet=False,
        )
