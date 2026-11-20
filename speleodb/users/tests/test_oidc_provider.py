from __future__ import annotations

import base64
import hashlib
import os
import secrets
import subprocess
import sys
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import parse_qs
from urllib.parse import quote_plus
from urllib.parse import urlsplit

import jwt
import pytest
from allauth.idp.oidc import models
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.test import Client
from django.urls import reverse
from lxml import html

from speleodb.users.oidc import _lock_token_owner
from speleodb.users.tests.factories import UserFactory
from speleodb.users.tests.factories import VerifiedUserFactory

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings


def assert_web_startup_rejects_key(pem: str, reason: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import config.wsgi"],
        env=os.environ
        | {
            "DJANGO_SETTINGS_MODULE": "config.settings.local",
            "DJANGO_READ_DOT_ENV_FILE": "false",
            "DJANGO_SECRET_KEY": "oidc-startup-tests-only",
            "DJANGO_OIDC_PRIVATE_KEY": pem,
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode != 0
    assert "DJANGO_OIDC_PRIVATE_KEY" in result.stderr
    assert reason in result.stderr
    if pem.strip():
        assert all(line not in result.stderr for line in pem.splitlines() if line)


def test_web_startup_rejects_a_non_rsa_private_key() -> None:
    pem = (
        ed25519.Ed25519PrivateKey.generate()
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode("ascii")
    )
    assert_web_startup_rejects_key(pem, "unencrypted RSA private key in PEM format")


def test_web_startup_rejects_encrypted_private_key() -> None:
    pem = (
        rsa.generate_private_key(public_exponent=65537, key_size=4096)
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(secrets.token_bytes(32)),
        )
        .decode("ascii")
    )
    assert_web_startup_rejects_key(pem, "unencrypted RSA private key in PEM format")


def test_local_launcher_check_requires_signing_key(settings: Settings) -> None:
    settings.IDP_OIDC_PRIVATE_KEY = ""
    with pytest.raises(SystemCheckError, match="DJANGO_OIDC_PRIVATE_KEY is missing"):
        call_command("check", "--deploy", "--tag", "oidc")


@pytest.mark.parametrize("key_size", [2048, 4608])
def test_web_startup_requires_exactly_4096_bits(key_size: int) -> None:
    pem = (
        rsa.generate_private_key(public_exponent=65537, key_size=key_size)
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode("ascii")
    )
    assert_web_startup_rejects_key(
        pem, f"has {key_size} bits. Exactly 4096 bits are required"
    )


@pytest.mark.django_db
def test_public_discovery_and_signing_key(
    client: Client, oidc_public_key: rsa.RSAPublicKey
) -> None:
    response = client.get("/.well-known/openid-configuration", secure=True)
    assert response.status_code == HTTPStatus.OK
    metadata = response.json()
    issuer = "https://testserver"
    assert metadata["issuer"] == issuer
    for field, route in (
        ("authorization_endpoint", "authorization"),
        ("token_endpoint", "token"),
        ("jwks_uri", "jwks"),
    ):
        assert metadata[field] == issuer + reverse(f"idp:oidc:{route}")
    assert {"client_secret_basic", "none"} <= set(
        metadata["token_endpoint_auth_methods_supported"]
    )
    assert "data:read" in metadata["scopes_supported"]
    (jwk,) = client.get(metadata["jwks_uri"], secure=True).json()["keys"]
    public_key = jwt.PyJWK.from_dict(jwk).key
    assert isinstance(public_key, rsa.RSAPublicKey)
    assert public_key.public_numbers() == oidc_public_key.public_numbers()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "destination", ["//elsewhere.test/", "https://elsewhere.test/"]
)
def test_login_ignores_external_continuation(client: Client, destination: str) -> None:
    user = VerifiedUserFactory.create()
    client.force_login(user)
    response = client.get(reverse("account_login"), {"next": destination})
    assert response["Location"] == reverse("private:user_dashboard")


@pytest.mark.django_db
def test_ordinary_login_keeps_dashboard_destination(client: Client) -> None:
    url = reverse("account_login", query={"next": reverse("home")})
    dashboard = reverse("private:user_dashboard")
    assert client.get(url).context["success_redirect"] == dashboard
    client.force_login(VerifiedUserFactory.create())
    assert client.get(url)["Location"] == dashboard


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_type", "callback"),
    [
        (models.Client.Type.CONFIDENTIAL, "https://atlas.example:65536/callback"),
        (models.Client.Type.CONFIDENTIAL, "org.example.atlas:/callback"),
        (models.Client.Type.PUBLIC, "http://atlas.example/callback"),
        (models.Client.Type.PUBLIC, "org.example.atlas://unknown/callback"),
    ],
)
def test_admin_cannot_register_invalid_callback(
    admin_client: Client, client_type: str, callback: str
) -> None:
    response = admin_client.post(
        reverse("admin:allauth_idp_oidc_client_add"),
        {"name": "Cave Atlas", "type": client_type, "redirect_uris": callback},
    )
    assert response.status_code == HTTPStatus.OK
    assert "redirect_uris" in response.context["adminform"].form.errors
    assert not models.Client.objects.filter(name="Cave Atlas").exists()


@pytest.mark.django_db
def test_staff_cannot_register_an_oidc_app(client: Client) -> None:
    user = UserFactory.create(is_staff=True)
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="allauth_idp_oidc", codename="add_client"
        )
    )
    client.force_login(user)
    url = reverse("admin:allauth_idp_oidc_client_add")
    data = {"name": "Cave Atlas", "redirect_uris": "https://atlas.example/callback"}
    assert client.post(url, data).status_code == HTTPStatus.FORBIDDEN


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("requested", "selected", "approved"),
    [
        ("openid email data:read", ["email"], False),
        ("openid email data:read", ["openid"], True),
        ("data:read", ["data:read"], True),
    ],
)
def test_consent_requires_identity_only_for_sign_in(
    client: Client, requested: str, selected: list[str], approved: bool
) -> None:
    user = VerifiedUserFactory.create()
    client.force_login(user)
    callback = "https://atlas.example/callback"
    website = models.Client(name="Cave Atlas", redirect_uris=callback)
    website.set_scopes(["openid", "email", "data:read"])
    website.set_grant_types(["authorization_code"])
    website.save()
    authorize = reverse("idp:oidc:authorization")
    response = client.get(
        authorize,
        {
            "client_id": website.pk,
            "response_type": "code",
            "redirect_uri": callback,
            "scope": requested,
            "state": "original",
            "code_challenge_method": "S256",
            "code_challenge": secrets.token_urlsafe(32),
        },
    )
    decision = client.post(
        authorize,
        {
            "request": response.context["form"]["request"].value(),
            "scopes": selected,
            "action": "grant",
        },
    )
    assert decision.status_code == HTTPStatus.FOUND
    redirect = urlsplit(decision["Location"])
    assert redirect._replace(query="").geturl() == callback
    query = parse_qs(redirect.query)
    assert query["state"] == ["original"]
    if approved:
        code = models.Token.objects.lookup(
            models.Token.Type.AUTHORIZATION_CODE, query["code"][0]
        )
        assert code is not None
        assert code.get_scopes() == selected
    else:
        assert query.get("error") == ["access_denied"]
        assert not models.Token.objects.filter(client=website, user=user).exists()


@pytest.mark.django_db
def test_pending_code_is_discarded_when_owner_is_disabled() -> None:
    user = VerifiedUserFactory.create()
    client = models.Client.objects.create(name="Cave Atlas")
    value = secrets.token_urlsafe(32)
    code = models.Token(
        type=models.Token.Type.AUTHORIZATION_CODE, user=user, client=client
    )
    code.set_value(value)
    code.save()

    user.is_active = False
    user.save(update_fields=["is_active"])
    _lock_token_owner(value, models.Token.Type.AUTHORIZATION_CODE)
    assert not models.Token.objects.filter(pk=code.pk).exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("oidc_public_key")
@pytest.mark.parametrize(
    ("client_type", "callback"),
    [
        (models.Client.Type.CONFIDENTIAL, "https://atlas.example/callback"),
        (models.Client.Type.PUBLIC, "https://atlas.example/oauth/callback/issuer"),
        (
            models.Client.Type.PUBLIC,
            "org.karstunderwater.speleomap:/oauth/callback/issuer",
        ),
    ],
)
def test_admin_registered_app_signs_in_and_reads_profile(
    client: Client,
    admin_client: Client,
    client_type: str,
    callback: str,
    settings: Settings,
) -> None:
    settings.CORS_ALLOW_ALL_ORIGINS = False
    origin = "https://atlas.example"
    callbacks = (
        [callback]
        if callback.startswith("https://")
        else [callback, f"{origin}/oauth/callback/issuer"]
    )
    registration = admin_client.post(
        reverse("admin:allauth_idp_oidc_client_add"),
        {
            "name": "Cave Atlas",
            "type": client_type,
            "redirect_uris": "\n".join(callbacks),
        },
        follow=True,
    )
    secrets_shown = html.fromstring(registration.content).xpath(
        '//li[contains(@class, "warning")]//input[@readonly]/@value'
    )
    website = models.Client.objects.get(name="Cave Atlas")
    assert website.type == client_type
    verifier = secrets.token_urlsafe(48)
    scopes = ["openid", "email", "data:read"]
    params = {
        "client_id": website.pk,
        "response_type": "code",
        "redirect_uri": callback,
        "scope": " ".join(scopes),
        "state": "original",
        "nonce": "test-nonce",
        "code_challenge_method": "S256",
        "code_challenge": base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        )
        .decode()
        .rstrip("="),
    }
    authorize = reverse("idp:oidc:authorization")
    assert (
        client.get(
            authorize, params | {"redirect_uri": callback + "?next=unregistered"}
        ).status_code
        == HTTPStatus.BAD_REQUEST
    )
    pkce_error = client.get(authorize, params | {"code_challenge_method": "plain"})
    assert pkce_error.status_code == HTTPStatus.FOUND
    failed_redirect = urlsplit(pkce_error["Location"])
    assert failed_redirect._replace(query="").geturl() == callback
    error = parse_qs(failed_redirect.query)
    assert error["error"] == ["invalid_request"]
    assert error["state"] == [params["state"]]
    login_page = client.get(authorize, params, follow=True)
    assert login_page.request["PATH_INFO"] == reverse("account_login")
    password = secrets.token_urlsafe(32)
    user = VerifiedUserFactory.create(password=password)
    login = client.post(
        reverse("headless:browser:account:login"),
        {"email": user.email, "password": password},
        content_type="application/json",
    )
    assert login.status_code == HTTPStatus.OK
    response = client.get(login_page.context["success_redirect"])
    consent = {"request": response.context["form"]["request"].value(), "scopes": scopes}
    approval = client.post(authorize, consent | {"action": "grant"})
    redirect = urlsplit(approval["Location"])
    assert redirect._replace(query="").geturl() == callback
    query = parse_qs(redirect.query)
    assert query["state"] == [params["state"]]
    code = query["code"][0]
    token_endpoint = reverse("idp:oidc:token")
    if client_type == models.Client.Type.PUBLIC:
        assert not secrets_shown
        headers = {"Origin": origin}
        client_auth = {"client_id": website.pk}
    else:
        (secret,) = secrets_shown
        credentials = base64.b64encode(
            f"{website.pk}:{quote_plus(secret)}".encode()
        ).decode()
        headers = {"Authorization": f"Basic {credentials}"}
        client_auth = {}
    exchange = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": callback,
    }
    exchange.update(client_auth)
    if client_type == models.Client.Type.CONFIDENTIAL:
        unauthenticated = client.post(
            token_endpoint, exchange | {"client_id": website.pk}
        )
        assert unauthenticated.json()["error"] == "invalid_client"
    assert (
        client.post(
            token_endpoint,
            exchange | {"code_verifier": secrets.token_urlsafe(48)},
            headers=headers,
        ).status_code
        == HTTPStatus.BAD_REQUEST
    )
    token_response = client.post(token_endpoint, exchange, headers=headers)
    assert token_response.status_code == HTTPStatus.OK
    if client_type == models.Client.Type.PUBLIC:
        assert token_response["Access-Control-Allow-Origin"] == origin
    tokens = token_response.json()
    jwks = client.get(reverse("idp:oidc:jwks")).json()
    claims = jwt.decode(
        tokens["id_token"],
        jwt.PyJWK.from_dict(jwks["keys"][0]).key,
        algorithms=["RS256"],
        audience=website.pk,
        issuer="http://testserver",
    )
    assert (
        claims["sub"],
        claims["nonce"],
        claims["email"],
        claims["email_verified"],
    ) == (str(user.pk), "test-nonce", user.email, True)
    api = Client()
    profile = reverse("api:v2:user-detail")
    assert (
        api.get(
            profile, headers={"Authorization": f"Bearer {tokens['id_token']}"}
        ).status_code
        == HTTPStatus.FORBIDDEN
    )
    bearer = {"Authorization": f"Bearer {tokens['access_token']}"}
    profile_response = api.get(profile, headers=bearer | {"Origin": origin})
    if client_type == models.Client.Type.PUBLIC:
        assert profile_response["Access-Control-Allow-Origin"] == origin
        preflight = api.options(
            profile,
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert preflight["Access-Control-Allow-Origin"] == origin
        unknown = api.get(profile, headers=bearer | {"Origin": origin + ".example"})
        assert "Access-Control-Allow-Origin" not in unknown
        assert "Access-Control-Allow-Origin" not in api.options(
            profile, headers={"Origin": origin, "Access-Control-Request-Method": "POST"}
        )
    assert profile_response.status_code == HTTPStatus.OK
    assert profile_response.json()["email"] == user.email

    refresh = {
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        **client_auth,
    }
    renewed = client.post(token_endpoint, refresh, headers=headers)
    assert renewed.status_code == HTTPStatus.OK
    rotated = renewed.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]
    assert set(rotated["scope"].split()) == set(scopes)
    assert (
        client.post(token_endpoint, refresh, headers=headers).json()["error"]
        == "invalid_grant"
    )

    bearer = {"Authorization": f"Bearer {rotated['access_token']}"}
    assert api.get(profile, headers=bearer).status_code == HTTPStatus.OK
    revoke = api.post(
        reverse("idp:oidc:revoke"),
        {"token": rotated["refresh_token"], **client_auth},
        headers=headers,
    )
    assert revoke.status_code == HTTPStatus.OK
    assert api.get(profile, headers=bearer).status_code == HTTPStatus.FORBIDDEN
    assert (
        api.post(
            token_endpoint,
            refresh | {"refresh_token": rotated["refresh_token"]},
            headers=headers,
        ).json()["error"]
        == "invalid_grant"
    )
