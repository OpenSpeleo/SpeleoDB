from rest_framework.authentication import BaseAuthentication
from rest_framework.authentication import TokenAuthentication


class DebugHeaderAuthentication(BaseAuthentication):
    """
    Custom authentication class for debugging request headers.
    """

    def authenticate(self, request):
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
