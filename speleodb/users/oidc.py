"""SpeleoDB's registration and consent policy for OIDC clients."""

from __future__ import annotations

import secrets
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any

from allauth.account import app_settings
from allauth.core.internal.httpkit import add_query_params
from allauth.idp.oidc.adapter import DefaultOIDCAdapter
from allauth.idp.oidc.models import Client
from allauth.idp.oidc.models import Token
from allauth.idp.oidc.views import AuthorizationView
from allauth.idp.oidc.views import RevokeView
from allauth.idp.oidc.views import TokenView
from django.conf import settings
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy

from speleodb.users.models import User

if TYPE_CHECKING:
    from allauth.idp.oidc.forms import AuthorizationForm
    from django.http import HttpRequest

DATA_READ_SCOPE = "data:read"
OIDC_LOGIN_SESSION_KEY = "oidc_login_redirect"


class SpeleoDBOIDCAdapter(DefaultOIDCAdapter):
    scope_display = DefaultOIDCAdapter.scope_display | {
        "openid": gettext_lazy("Share your user ID (required to sign in)"),
        DATA_READ_SCOPE: gettext_lazy(
            "Read the SpeleoDB data you can access, including after you leave "
            "this website"
        ),
    }

    def generate_client_secret(self) -> str:
        # OAuth clients form-encode Basic credentials. Hex stays identical when
        # encoded, including for allauth's literal Basic credential comparison.
        return secrets.token_hex(32)

    def get_issuer(self) -> str:
        return getattr(settings, "SPELEODB_OIDC_ISSUER", "") or super().get_issuer()

    def populate_server_metadata(self, data: dict[str, str | list[str]]) -> None:
        data.update(
            scopes_supported=["openid", "email", DATA_READ_SCOPE],
            response_types_supported=["code"],
            grant_types_supported=["authorization_code", "refresh_token"],
        )
        data.pop("device_authorization_endpoint", None)


class WebsiteAuthorizationView(AuthorizationView):
    template_name = "auth/authorize_website.html"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        # The library also accepts extra query parameters and variable loopback
        # ports for native clients. Require the registered callback verbatim.
        client = Client.objects.filter(pk=request.GET.get("client_id")).first()
        redirect_uris = request.GET.getlist("redirect_uri")
        if (
            client is None
            or len(redirect_uris) != 1
            or redirect_uris[0] not in client.get_redirect_uris()
        ):
            return HttpResponseBadRequest(
                "Unknown client or unregistered callback URL."
            )
        if (
            not request.GET.get("code_challenge")
            or request.GET.get("code_challenge_method") != "S256"
        ):
            params = {
                "error": "invalid_request",
                "error_description": "Sign in with SpeleoDB requires S256 PKCE.",
            }
            if state := request.GET.get("state"):
                params["state"] = state
            return HttpResponse(
                status=HTTPStatus.FOUND,
                headers={"Location": add_query_params(redirect_uris[0], params)},
            )
        response = super().get(request, *args, **kwargs)
        if request.user.is_authenticated:
            request.session.pop(OIDC_LOGIN_SESSION_KEY, None)
        elif isinstance(response, HttpResponseRedirect) and response.url.startswith(
            reverse("account_login") + "?"
        ):
            # Account verification and password reset return to the plain login
            # page. Remember the provider's own login URL for that same browser.
            request.session[OIDC_LOGIN_SESSION_KEY] = {
                "url": response.url,
                "expires_at": timezone.now().timestamp() + app_settings.LOGIN_TIMEOUT,
            }
        return response

    def form_valid(self, form: AuthorizationForm) -> HttpResponse:
        if "openid" in self._scopes and "openid" not in form.cleaned_data["scopes"]:
            return self._respond_with_access_denied()
        return super().form_valid(form)


def _lock_token_owner(value: str | None, *types: Token.Type) -> None:
    if value:
        # ATOMIC_REQUESTS holds the user row through validation and issuance.
        # It survives rotation and is shared with profile revocation.
        tokens = Token.objects.valid().by_value(value).filter(type__in=types)
        owner_active = (
            User.objects.select_for_update(no_key=True)
            .filter(pk__in=tokens.values("user_id"))
            .values_list("is_active", flat=True)
            .first()
        )
        if owner_active is False and types == (Token.Type.AUTHORIZATION_CODE,):
            # Allauth checks account activity on refresh, but accepts a pending
            # code if its user still exists. Let it reject this as invalid_grant.
            tokens.delete()


class WebsiteTokenView(TokenView):
    def post(self, request: HttpRequest) -> HttpResponse:
        grant = request.POST.get("grant_type")
        if grant == Client.GrantType.AUTHORIZATION_CODE:
            _lock_token_owner(request.POST.get("code"), Token.Type.AUTHORIZATION_CODE)
        elif grant == Client.GrantType.REFRESH_TOKEN:
            _lock_token_owner(
                request.POST.get("refresh_token"), Token.Type.REFRESH_TOKEN
            )
        return super().post(request)


class WebsiteRevokeView(RevokeView):
    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        _lock_token_owner(
            request.POST.get("token"), Token.Type.ACCESS_TOKEN, Token.Type.REFRESH_TOKEN
        )
        return super().post(request, *args, **kwargs)
