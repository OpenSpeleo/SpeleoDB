# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import pytest
from allauth.account.signals import password_changed
from allauth.account.signals import password_reset
from allauth.account.signals import user_logged_in
from allauth.account.signals import user_signed_up

# This one should come from django not allauth
from django.contrib.auth.signals import user_logged_out

from speleodb.common.enums import UserAction
from speleodb.common.enums import UserApplication
from speleodb.users.models import AccountEvent
from speleodb.users.signals import api_auth_success
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import RequestFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("signal", "expected_action"),
    [
        (user_logged_in, UserAction.LOGIN),
        (user_logged_out, UserAction.LOGOUT),
        (user_signed_up, UserAction.SIGNUP),
        (password_changed, UserAction.PASSWORD_CHANGED),
        (password_reset, UserAction.PASSWORD_RESET),
    ],
)
def test_allauth_signal_creates_website_account_event(
    rf: RequestFactory,
    signal: Any,
    expected_action: UserAction,
) -> None:
    user = UserFactory.create()
    request = rf.get(
        "/",
        HTTP_USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        REMOTE_ADDR="192.0.2.10",
    )

    signal.send(sender=user.__class__, user=user, request=request)

    event = AccountEvent.objects.get()
    assert event.user == user
    assert event.action == expected_action
    assert event.application == UserApplication.WEBSITE
    assert event.ip_addr == "192.0.2.10"
    assert event.user_agent == "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("user_agent", "expected_application"),
    [
        ("Ariane/3.2.0 (iPhone)", UserApplication.ARIANE_APP),
        ("Compass/1.0.0 (Android)", UserApplication.COMPASS_APP),
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
            UserApplication.IOS_APP,
        ),
        (
            "Mozilla/5.0 (Linux; Android 14; Pixel 8)",
            UserApplication.ANDROID_APP,
        ),
        ("Mozilla/5.0 (X11; Linux x86_64)", UserApplication.UNKNOWN),
    ],
)
def test_api_auth_success_signal_detects_application(
    rf: RequestFactory, user_agent: str, expected_application: str
) -> None:
    user = UserFactory.create()
    request = rf.get(
        "/",
        HTTP_USER_AGENT=user_agent,
        REMOTE_ADDR="198.51.100.13",
    )

    api_auth_success.send(sender=user.__class__, user=user, request=request)

    event = AccountEvent.objects.get()
    assert event.action == UserAction.LOGIN
    assert event.application == expected_application
    assert event.ip_addr == "198.51.100.13"
    assert event.user_agent == user_agent


@pytest.mark.django_db
def test_api_auth_success_signal_prefers_x_forwarded_for(rf: RequestFactory) -> None:
    user = UserFactory.create()
    request = rf.get(
        "/",
        HTTP_USER_AGENT="app-client",
        REMOTE_ADDR="10.0.0.25",
        HTTP_X_FORWARDED_FOR="203.0.113.5, 10.0.0.25",
    )

    api_auth_success.send(sender=user.__class__, user=user, request=request)

    event = AccountEvent.objects.get()
    assert event.ip_addr == "203.0.113.5"


@pytest.mark.django_db
def test_api_auth_success_signal_uses_empty_ip_when_invalid(rf: RequestFactory) -> None:
    user = UserFactory.create()
    request = rf.get(
        "/",
        HTTP_USER_AGENT="app-client",
        HTTP_X_FORWARDED_FOR="not-an-ip",
        REMOTE_ADDR="",
    )

    api_auth_success.send(sender=user.__class__, user=user, request=request)

    event = AccountEvent.objects.get()
    assert not event.ip_addr


@pytest.mark.django_db
def test_api_auth_success_signal_accepts_none_request() -> None:
    user = UserFactory.create()

    api_auth_success.send(sender=user.__class__, user=user, request=None)

    event = AccountEvent.objects.get()
    assert not event.ip_addr
    assert event.user_agent == ""
