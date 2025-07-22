# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

import pytest
from django.urls import resolve
from django.urls import reverse


@pytest.mark.parametrize(
    ("name", "path", "kwargs"),
    [
        # General routes
        ("home", "", None),
        ("about", "about/", None),
        ("people", "people/", None),
        ("roadmap", "roadmap/", None),
        ("changelog", "changelog/", None),
        ("terms_and_conditions", "terms_and_conditions/", None),
        ("privacy_policy", "privacy_policy/", None),
        # Webviews
        ("webview_ariane", "webview/ariane/", None),
        # User Auth Management
        ("account_login", "login/", None),
        ("account_logout", "logout/", None),
        ("account_signup", "signup/", None),
        (
            "account_confirm_email",
            "account/confirm-email/{key}/",
            {"key": "abc123-def456:ghi789"},
        ),
        ("account_reset_password", "account/password/reset/", None),
        (
            "account_reset_password_from_key",
            "account/password/reset/{uidb36}-{key}/",
            {"uidb36": "test@speleodb.org", "key": "abc123-def456"},
        ),
    ],
)
def test_routes(name: str, path: str, kwargs: Any | None) -> None:
    path = f"/{path}" if kwargs is None else f"/{path.format(**kwargs)}"

    # Test reverse URL generation
    if kwargs:
        assert reverse(name, kwargs=kwargs) == path
    else:
        assert reverse(name) == path

    # Test resolve to view name
    assert resolve(path).view_name == name
