"""Configured allauth flows through real browser and app HTTP transports."""

from __future__ import annotations

import json
from typing import Any
from typing import cast
from uuid import uuid4

import pytest
from allauth.account import app_settings as account_settings
from allauth.account.models import EmailAddress
from allauth.account.models import EmailConfirmationHMAC
from allauth.account.utils import user_pk_to_url_str
from allauth.headless.internal.sessionkit import authenticate_by_x_session_token
from django.contrib.sessions.models import Session
from django.test import Client
from django.test import override_settings
from rest_framework import status

from speleodb.testing.api_contract import assert_api_response
from speleodb.testing.api_contract import contract_schema
from speleodb.users.models import User
from speleodb.users.tests.factories import UserFactory


@pytest.mark.django_db
@pytest.mark.parametrize("client_kind", ["browser", "app"])
@pytest.mark.parametrize("mount", ["/_allauth/", "/api/auth/"])
@pytest.mark.parametrize(
    ("suffix", "method", "action", "authenticated", "first_status"),
    [
        ("auth/login", "POST", "login", False, status.HTTP_400_BAD_REQUEST),
        ("auth/signup", "POST", "signup", False, status.HTTP_400_BAD_REQUEST),
        ("auth/password/request", "POST", "reset_password", False, status.HTTP_200_OK),
        (
            "auth/password/reset",
            "GET",
            "reset_password_from_key",
            False,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "auth/password/reset",
            "POST",
            "reset_password_from_key",
            False,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "auth/reauthenticate",
            "POST",
            "reauthenticate",
            True,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            "account/password/change",
            "POST",
            "change_password",
            True,
            status.HTTP_400_BAD_REQUEST,
        ),
        ("account/email", "GET", "manage_email", True, status.HTTP_200_OK),
        ("account/email", "POST", "manage_email", True, status.HTTP_400_BAD_REQUEST),
        ("account/email", "PUT", "manage_email", True, status.HTTP_400_BAD_REQUEST),
        ("account/email", "PATCH", "manage_email", True, status.HTTP_400_BAD_REQUEST),
        ("account/email", "DELETE", "manage_email", True, status.HTTP_400_BAD_REQUEST),
    ],
)
def test_configured_rate_limit_responses(
    *,
    client_kind: str,
    mount: str,
    suffix: str,
    method: str,
    action: str,
    authenticated: bool,
    first_status: int,
) -> None:
    """Consume actual limiters using supported settings and isolated real cache."""
    caches = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": f"allauth-contract-{uuid4()}",
        }
    }
    rate = "1/m/user" if authenticated else "1/m/ip"
    with override_settings(CACHES=caches, ACCOUNT_RATE_LIMITS={action: rate}):
        client = Client()
        headers: dict[str, str] = {}
        if authenticated:
            user = cast("User", UserFactory())
            EmailAddress.objects.create(
                user=user, email=user.email, verified=True, primary=True
            )
            client.force_login(user)
            if client_kind == "app":
                token = client.session.session_key
                assert token is not None
                headers["X-Session-Token"] = token
                client.cookies.clear()
        payload = (
            {"email": "rate-limit-contract@example.com"}
            if suffix == "auth/password/request"
            else {}
        )
        second_status = (
            first_status if method == "GET" else status.HTTP_429_TOO_MANY_REQUESTS
        )
        for expected in (first_status, second_status):
            response = client.generic(
                method,
                f"{mount}{client_kind}/v1/{suffix}",
                data=json.dumps(payload) if method != "GET" else "",
                content_type="application/json",
                headers=headers,
            )
            assert response.status_code == expected, response.content
            assert_api_response(response)
        assert response.json()["status"] == second_status
        assert "Retry-After" not in response.headers


def test_unthrottled_and_disabled_auth_handlers_do_not_advertise_rate_limits() -> None:
    document = contract_schema()
    for path, item in document["paths"].items():
        if not path.startswith("/_allauth/"):
            continue
        if "get" in item:
            assert "429" not in item["get"]["responses"]
        if any(
            part in path
            for part in ("/config", "/auth/session", "/phone", "/auth/code/confirm")
        ) or path.endswith("/auth/email/verify/resend"):
            for method in ("get", "post", "delete"):
                if method in item:
                    assert "429" not in item[method]["responses"]


@pytest.mark.django_db
@pytest.mark.parametrize("client_kind", ["browser", "app"])
@pytest.mark.parametrize("mount", ["/_allauth/", "/api/auth/"])
def test_configured_account_lifecycle(client_kind: str, mount: str) -> None:
    client = Client()
    headers: dict[str, str] = {}
    password = "ContractPassword!8394"  # noqa: S105 - Test account only.
    email = f"contract-{client_kind}@example.com"
    second_email = f"contract-second-{client_kind}@example.com"

    def call(
        method: str,
        suffix: str,
        payload: dict[str, Any] | None = None,
        expected: int = status.HTTP_200_OK,
        extra: dict[str, str] | None = None,
    ) -> Any:
        response = client.generic(
            method,
            f"{mount}{client_kind}/v1/{suffix}",
            data=json.dumps(payload) if payload is not None else "",
            content_type="application/json",
            headers={**headers, **(extra or {})},
        )
        if "X-Session-Token" in headers:
            assert (
                response.wsgi_request.headers.get("X-Session-Token")
                == headers["X-Session-Token"]
            )
        assert response.status_code == expected, response.content
        assert_api_response(response)
        if client_kind == "app":
            token = response.json().get("meta", {}).get("session_token")
            if token:
                headers["X-Session-Token"] = token
        return response

    config = call("GET", "config").json()["data"]
    assert config["account"]["login_methods"] == ["email"]
    signup = call(
        "POST",
        "auth/signup",
        {
            "email": email,
            "password": password,
            "name": "Contract Tester",
            "country": "US",
        },
        expected=status.HTTP_401_UNAUTHORIZED,
    )
    assert signup.json()["meta"]["is_authenticated"] is False
    user = User.objects.get(email=email)
    assert user.name == "Contract Tester"
    assert user.country == "US"
    address = EmailAddress.objects.get(user=user, email=email)
    key = EmailConfirmationHMAC(address).key
    call("GET", "auth/email/verify", extra={"X-Email-Verification-Key": key})
    call(
        "POST", "auth/email/verify", {"key": key}, expected=status.HTTP_401_UNAUTHORIZED
    )
    address.refresh_from_db()
    assert address.verified
    login = call("POST", "auth/login", {"email": email, "password": password})
    assert login.json()["data"]["user"]["id"] == user.id
    assert login.json()["data"]["user"]["email"] == email
    if client_kind == "app":
        session = Session.objects.get(session_key=headers["X-Session-Token"])
        assert session.get_decoded().get("_auth_user_id") == str(user.pk), (
            session.get_decoded()
        )
        authenticated = authenticate_by_x_session_token(headers["X-Session-Token"])
        assert authenticated is not None
        assert authenticated[0].pk == user.pk
    call("GET", "auth/session")
    call("GET", "account/phone", expected=status.HTTP_409_CONFLICT)
    head = client.head(f"{mount}{client_kind}/v1/account/phone", headers=headers)
    assert head.status_code == status.HTTP_409_CONFLICT
    assert head.content == b""
    call(
        "POST",
        "account/phone",
        {"phone": "+15555550123"},
        expected=status.HTTP_409_CONFLICT,
    )
    call(
        "POST",
        "auth/phone/verify",
        {"code": "123456"},
        expected=status.HTTP_409_CONFLICT,
    )
    call("POST", "auth/phone/verify/resend", expected=status.HTTP_409_CONFLICT)
    call(
        "POST",
        "auth/code/confirm",
        {"code": "123456"},
        expected=status.HTTP_409_CONFLICT,
    )
    call("POST", "auth/email/verify/resend", expected=status.HTTP_409_CONFLICT)
    if client_kind == "app":
        call(
            "POST",
            "tokens/refresh",
            {"refresh_token": "unavailable"},
            expected=status.HTTP_400_BAD_REQUEST,
        )
    call("POST", "auth/reauthenticate", {"password": password})
    call("GET", "account/email")
    call("POST", "account/email", {"email": second_email})
    # Use a separate unverified address to avoid the real resend cooldown on the
    # email just added. This fixture exercises the same configured mail backend.
    third_email = f"contract-third-{client_kind}@example.com"
    EmailAddress.objects.create(user=user, email=third_email, verified=False)
    call("PUT", "account/email", {"email": third_email})
    second = EmailAddress.objects.get(user=user, email=second_email)
    second.verified = True
    second.save(update_fields=["verified"])
    call("PATCH", "account/email", {"email": second_email, "primary": True})
    call("DELETE", "account/email", {"email": third_email})
    call("DELETE", "auth/session", expected=status.HTTP_401_UNAUTHORIZED)
    headers.clear()
    client = Client()
    call("POST", "auth/login", {"email": second_email, "password": password})
    changed = "ChangedContractPassword!9834"
    call(
        "POST",
        "account/password/change",
        {"current_password": password, "new_password": changed},
        expected=status.HTTP_401_UNAUTHORIZED,
    )
    user.refresh_from_db()
    assert user.check_password(changed)
    headers.clear()
    client = Client()
    call("POST", "auth/password/request", {"email": second_email})
    reset_token = account_settings.PASSWORD_RESET_TOKEN_GENERATOR().make_token(user)
    reset_key = f"{user_pk_to_url_str(user)}-{reset_token}"
    call("GET", "auth/password/reset", extra={"X-Password-Reset-Key": reset_key})
    final_password = "ResetContractPassword!3984"  # noqa: S105 - Test account only.
    call(
        "POST",
        "auth/password/reset",
        {"key": reset_key, "password": final_password},
        expected=status.HTTP_401_UNAUTHORIZED,
    )
    user.refresh_from_db()
    assert user.check_password(final_password)


@pytest.mark.django_db
@pytest.mark.parametrize("mount", ["/_allauth/", "/api/auth/"])
def test_app_session_rejects_cookie_identity_and_invalid_token(mount: str) -> None:

    user = cast("User", UserFactory())
    client = Client()
    client.force_login(user)
    # App authentication must not inherit an authenticated browser cookie.
    response = client.get(f"{mount}app/v1/auth/session")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_api_response(response)
    response = client.get(
        f"{mount}app/v1/auth/session",
        headers={"X-Session-Token": "invalid-session-token"},
    )
    assert response.status_code == status.HTTP_410_GONE
    assert_api_response(response)


@pytest.mark.django_db
@pytest.mark.parametrize("mount", ["/_allauth/", "/api/auth/"])
def test_browser_session_retains_hijack_metadata(mount: str) -> None:

    user = cast("User", UserFactory())
    client = Client()
    client.force_login(user)
    session = client.session
    session["hijack_history"] = ["original-administrator"]
    session.save()
    response = client.get(f"{mount}browser/v1/auth/session")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["user"]["id"] == user.pk
    assert getattr(response.wsgi_request.user, "is_hijacked", False)
    assert_api_response(response)
