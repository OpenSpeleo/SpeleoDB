"""Browser access for registered public OIDC clients."""

from __future__ import annotations

from typing import TYPE_CHECKING

from allauth.idp.oidc.models import Client
from corsheaders.signals import check_request_enabled
from django.dispatch import receiver
from django.urls import reverse

from speleodb.users.oidc_authentication import allows_delegated_read

if TYPE_CHECKING:
    from django.http import HttpRequest


@receiver(check_request_enabled)
def allow_public_client_origin(request: HttpRequest, **kwargs: object) -> bool:
    origin = request.headers.get("Origin")
    if not origin:
        return False
    method = (
        request.headers.get("Access-Control-Request-Method")
        if request.method == "OPTIONS"
        else request.method
    )
    path = request.path_info
    if not allows_delegated_read(method, path) and not (
        (method == "GET" and request.path == reverse("idp:oidc:userinfo"))
        or (
            method == "POST"
            and request.path in {reverse("idp:oidc:token"), reverse("idp:oidc:revoke")}
        )
    ):
        return False
    apps = Client.objects.filter(
        type=Client.Type.PUBLIC, cors_origins__contains=origin
    ).only("cors_origins")
    return any(origin in app.get_cors_origins() for app in apps)
