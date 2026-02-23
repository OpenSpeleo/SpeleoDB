# -*- coding: utf-8 -*-

from __future__ import annotations

from ipaddress import ip_address
from typing import TYPE_CHECKING
from typing import Any

from allauth.account.signals import password_changed
from allauth.account.signals import password_reset
from allauth.account.signals import user_logged_in
from allauth.account.signals import user_signed_up

# This one should come from django not allauth
from django.contrib.auth.signals import user_logged_out
from django.dispatch import Signal
from django.dispatch import receiver

from speleodb.common.enums import UserAction
from speleodb.common.enums import UserApplication
from speleodb.users.models import AccountEvent

if TYPE_CHECKING:
    from django.http import HttpRequest

    from speleodb.users.models import User


api_auth_success = Signal()
auth_token_refresh = Signal()


def _extract_ip_address(request: HttpRequest | None) -> str | None:
    if request is None:
        return None

    meta = getattr(request, "META", {})
    x_forwarded_for = meta.get("HTTP_X_FORWARDED_FOR", "")

    client_ip: str
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(",")[0].strip()
    else:
        client_ip = meta.get("REMOTE_ADDR", "")

    if not client_ip:
        return None

    try:
        ip_address(client_ip)
    except ValueError:
        return None

    return client_ip


def _extract_user_agent(request: HttpRequest | None) -> str:
    if request is None:
        return ""

    return getattr(request, "META", {}).get("HTTP_USER_AGENT", "")  # type: ignore[no-any-return]


def _infer_api_application(user_agent: str) -> UserApplication:
    normalized_user_agent = user_agent.lower()

    if any(pattern in normalized_user_agent for pattern in ("ariane", "java")):
        return UserApplication.ARIANE_APP

    if any(pattern in normalized_user_agent for pattern in ("compass", "tauri")):
        return UserApplication.COMPASS_APP

    if any(
        pattern in normalized_user_agent
        for pattern in ("iphone", "ipad", "ipod", "ios")
    ):
        return UserApplication.IOS_APP

    if "android" in normalized_user_agent:
        return UserApplication.ANDROID_APP

    return UserApplication.UNKNOWN


def _create_account_event(
    *,
    user: User,
    action: UserAction,
    request: HttpRequest | None,
    application: UserApplication,
) -> AccountEvent:
    return AccountEvent.objects.create(
        user=user,
        ip_addr=_extract_ip_address(request),
        user_agent=_extract_user_agent(request),
        action=action,
        application=application,
    )


# =========================================================================== #
# Website Actions
# =========================================================================== #


@receiver(user_logged_in)
def post_login(sender: Any, user: User, request: HttpRequest, **kwargs: Any) -> None:
    _create_account_event(
        user=user,
        action=UserAction.LOGIN,
        request=request,
        application=UserApplication.WEBSITE,
    )


@receiver(user_logged_out)
def post_logout(
    sender: Any, request: HttpRequest, user: User | None, **kwargs: Any
) -> None:
    if user is None:
        return

    _create_account_event(
        user=user,
        action=UserAction.LOGOUT,
        request=request,
        application=UserApplication.WEBSITE,
    )


@receiver(user_signed_up)
def post_signup(sender: Any, request: HttpRequest, user: User, **kwargs: Any) -> None:
    _create_account_event(
        user=user,
        action=UserAction.SIGNUP,
        request=request,
        application=UserApplication.WEBSITE,
    )


@receiver(password_changed)
def post_password_changed(
    sender: Any, request: HttpRequest, user: User, **kwargs: Any
) -> None:
    _create_account_event(
        user=user,
        action=UserAction.PASSWORD_CHANGED,
        request=request,
        application=UserApplication.WEBSITE,
    )


@receiver(password_reset)
def post_password_reset(
    sender: Any, request: HttpRequest, user: User, **kwargs: Any
) -> None:
    _create_account_event(
        user=user,
        action=UserAction.PASSWORD_RESET,
        request=request,
        application=UserApplication.WEBSITE,
    )


# =========================================================================== #
# API Actions
# =========================================================================== #


@receiver(api_auth_success)
def post_api_auth_success(
    sender: Any,
    user: User,
    request: HttpRequest | None,
    **kwargs: Any,
) -> None:
    _create_account_event(
        user=user,
        action=UserAction.LOGIN,
        request=request,
        application=_infer_api_application(_extract_user_agent(request)),
    )


@receiver(auth_token_refresh)
def post_auth_token_refresh(
    sender: Any,
    user: User,
    request: HttpRequest | None,
    **kwargs: Any,
) -> None:
    _create_account_event(
        user=user,
        action=UserAction.TOKEN_REFRESH,
        request=request,
        application=_infer_api_application(_extract_user_agent(request)),
    )
