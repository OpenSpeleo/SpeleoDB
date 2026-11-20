"""Delegated access to the SpeleoDB data API."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from allauth.idp.oidc import models
from allauth.idp.oidc.contrib.rest_framework import authentication
from django.conf import settings
from django.urls import get_script_prefix
from django.urls import reverse
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.exceptions import PermissionDenied

from speleodb.users.oidc import DATA_READ_SCOPE

if TYPE_CHECKING:
    from django.http import HttpRequest
    from drf_spectacular.openapi import AutoSchema

    from speleodb.users.models import User


def allows_delegated_read(method: str | None, path: str) -> bool:
    return (
        method == "GET"
        and path.startswith("/api/v2/")
        and get_script_prefix() + path.lstrip("/") != reverse("api:v2:user-auth-token")
    )


class DelegatedReadAuthentication(authentication.TokenAuthentication):
    def authenticate(self, request: HttpRequest) -> tuple[User, models.Token] | None:
        parts = request.headers.get("Authorization", "").strip().split(maxsplit=1)
        if not parts or parts[0].lower() != "bearer":
            return None
        if len(parts) == 1:
            raise AuthenticationFailed("Invalid token.")
        value = parts[1]

        if allows_delegated_read(request.method, request.path_info):
            result = super().authenticate(request)
            if result is not None:
                user, token = result
                if (
                    token is None
                    or user is None
                    or DATA_READ_SCOPE not in token.get_scopes()
                ):
                    raise PermissionDenied("The data:read scope is required.")
                return user, token

        elif models.Token.objects.by_value(value).exists():
            raise PermissionDenied("This endpoint does not accept OIDC access tokens.")

        # Personal tokens share the Bearer scheme. Let their authenticator
        # handle them, preserving session precedence for a valid personal token.
        # An invalid or revoked bearer must never inherit a browser session.
        if (
            settings.SESSION_COOKIE_NAME in request.COOKIES
            and not Token.objects.filter(key=value).exists()
        ):
            raise AuthenticationFailed("Invalid token.")
        return None


class DelegatedReadScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = DelegatedReadAuthentication
    name = "speleodbOIDC"

    @classmethod
    def requirements(cls, method: str, path: str) -> list[dict[str, list[str]]]:
        if allows_delegated_read(method, path):
            return [{cls.name: [DATA_READ_SCOPE]}]
        return []

    def get_security_requirement(
        self, auto_schema: AutoSchema
    ) -> list[dict[str, list[str]]]:
        return self.requirements(auto_schema.method, auto_schema.path)

    def get_security_definition(self, auto_schema: AutoSchema) -> dict[str, Any]:
        return {
            "type": "openIdConnect",
            "openIdConnectUrl": reverse("idp:oidc:configuration"),
        }
