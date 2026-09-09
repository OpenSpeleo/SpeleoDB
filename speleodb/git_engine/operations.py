from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import unquote
from urllib.parse import urlsplit

from django.conf import settings
from git.exc import GitCommandError

from speleodb.git_engine.exceptions import GitBaseError
from speleodb.utils.helpers import retry_with_backoff

if TYPE_CHECKING:
    from collections.abc import Callable


def retry_git_operation[RT](
    operation: Callable[..., RT],
    *args: Any,
    remote_url: str,
    action: str,
    **kwargs: Any,
) -> RT:
    """Retry remote Git commands without exposing credentials to retry logs."""
    parsed_url = urlsplit(remote_url)
    raw_userinfo = (
        parsed_url.netloc.rpartition("@")[0] if "@" in parsed_url.netloc else ""
    )
    raw_credential = (
        raw_userinfo.partition(":")[2] if ":" in raw_userinfo else raw_userinfo
    )
    credential_variants = {
        credential
        for credential in (raw_credential, unquote(raw_credential))
        if credential
    }
    credential_url_pattern = re.compile(
        r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^/@\s'\"<>]+@",
        flags=re.IGNORECASE,
    )

    def redact_credentials(value: object) -> str:
        redacted = str(value)
        for credential in sorted(credential_variants, key=len, reverse=True):
            redacted = redacted.replace(credential, "[REDACTED]")
        return credential_url_pattern.sub(r"\g<scheme>", redacted)

    def run_with_sanitized_errors() -> RT:
        sanitized_error: GitBaseError
        try:
            return operation(*args, **kwargs)
        except GitCommandError as error:
            sanitized_error = GitBaseError(
                f"Impossible to {action} repository: "
                f"url={redact_credentials(remote_url)!r}. {redact_credentials(error)}"
            )
        # Outside the handler: no credential-bearing context survives either.
        raise sanitized_error from None

    return retry_with_backoff(
        run_with_sanitized_errors,
        retries=settings.DJANGO_GIT_RETRY_ATTEMPTS,
        exc_types=(GitBaseError,),
        base_delay=1.0,
    )
