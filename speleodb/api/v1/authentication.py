from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.authentication import BasicAuthentication
from rest_framework.authentication import TokenAuthentication

if TYPE_CHECKING:
    from rest_framework.authtoken.models import Token
    from rest_framework.request import Request


class DebugHeaderAuthentication(BaseAuthentication):
    """
    Custom authentication class for debugging request headers.
    """

    def authenticate(self, request: Request) -> None:
        """
        Logs the entire request headers and returns None.
        """
        # Log all headers for debugging purposes
        print(f"Request headers: {request.headers=}")  # noqa: T201

        # This authentication class does not perform any actual authentication.
        # Return None to allow other authenticators to handle the request.
        return None  # noqa: PLR1711, RET501


class BearerAuthentication(TokenAuthentication):
    """
    Simple token based authentication using utvsapitoken.

    Clients should authenticate by passing the token key in the 'Authorization'
    HTTP header, prepended with the string 'Bearer '.  For example:

    Authorization: Bearer 956e252a-513c-48c5-92dd-bfddc364e812
    """

    keyword = "Bearer"


class GitOAuth2Authentication(BasicAuthentication):
    """
    A combination of `BasicAuthentication` and `TokenAuthentication`.
    Specific for git `oauth2:<token>` authentication scheme.
    """

    model: type[Token] | None = None

    def get_model(self) -> type[Token]:
        if self.model is not None:
            return self.model
        from rest_framework.authtoken.models import Token

        return Token

    def authenticate_credentials(  # type: ignore[override]
        self,
        userid: Any,
        password: str,
        request: Request | None = None,
    ) -> tuple[Any, Token]:
        model = self.get_model()
        try:
            token = model.objects.select_related("user").get(key=password)
        except model.DoesNotExist as e:
            raise exceptions.AuthenticationFailed("Invalid token.") from e

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed("User inactive or deleted.")

        return (token.user, token)
