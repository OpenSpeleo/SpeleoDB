"""GitLab transport with finite attempts and application-owned retry delays."""

from __future__ import annotations

import logging
import math
import time
from contextvars import ContextVar
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from typing import override

import gitlab
from gitlab.const import RETRYABLE_TRANSIENT_ERROR_CODES
from gitlab.exceptions import GitlabHttpError
from requests.exceptions import ChunkedEncodingError
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout

if TYPE_CHECKING:
    from contextvars import Token
    from typing import BinaryIO

    from requests import Response

logger = logging.getLogger(__name__)


class BoundedGitlabClient(gitlab.Gitlab):
    """Keep SDK HTTP/error handling, with no SDK retries or header-driven sleeps."""

    def __init__(
        self,
        url: str,
        *,
        private_token: str,
        keep_base_url: bool = False,
        max_attempts: int = 5,
        timeout: float = 30,
        base_delay: float = 1,
        max_delay: float = 30,
        retry_transient_errors: bool | None = None,
    ) -> None:
        if (
            isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int)
            or max_attempts < 1
        ):
            raise ValueError("GitLab max_attempts must be a positive integer")
        if not all(
            math.isfinite(value) and value > 0
            for value in (timeout, base_delay, max_delay)
        ):
            raise ValueError(
                "GitLab timeouts and retry delays must be finite and positive"
            )
        self._max_attempts: int = max_attempts
        self._request_timeout: float = timeout
        self._base_delay: float = min(base_delay, max_delay)
        self._max_delay: float = max_delay
        self._retry_transient_errors: bool | None = retry_transient_errors
        self._resource_lock_conflict: ContextVar[bool] = ContextVar(
            "gitlab_resource_lock_conflict", default=False
        )
        super().__init__(
            url,
            private_token=private_token,
            keep_base_url=keep_base_url,
            timeout=timeout,
            retry_transient_errors=False,
        )
        self.session.hooks["response"].append(self._capture_resource_lock_conflict)

    def _capture_resource_lock_conflict(
        self, response: Response, **kwargs: Any
    ) -> None:
        # The SDK omits the HTTP reason from GitlabHttpError. Keep only this
        # retry classification, isolated from other callers sharing the client.
        self._resource_lock_conflict.set(
            response.status_code == HTTPStatus.CONFLICT
            and "Resource lock" in (response.reason or "")
        )

    @override
    def http_request(
        self,
        verb: str,
        path: str,
        query_data: dict[str, Any] | None = None,
        post_data: dict[str, Any] | bytes | BinaryIO | None = None,
        raw: bool = False,
        streamed: bool = False,
        files: dict[str, Any] | None = None,
        timeout: float | None = None,
        obey_rate_limit: bool = True,
        retry_transient_errors: bool | None = None,
        max_retries: int | None = None,
        extra_headers: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response:
        if max_retries is not None and (
            isinstance(max_retries, bool)
            or not isinstance(max_retries, int)
            or max_retries < 0
        ):
            raise ValueError("GitLab max_retries must be a nonnegative integer")
        attempts: int = min(
            self._max_attempts,
            self._max_attempts if max_retries is None else max_retries + 1,
        )
        request_timeout: float = self._request_timeout if timeout is None else timeout
        if not math.isfinite(request_timeout) or request_timeout <= 0:
            raise ValueError("GitLab timeout must be finite and positive")
        request_timeout = min(request_timeout, self._request_timeout)
        retry_transient: bool | None = (
            self._retry_transient_errors
            if retry_transient_errors is None
            else retry_transient_errors
        )
        if retry_transient is None:
            retry_transient = verb.upper() in {"GET", "HEAD"}
        delay: float = self._base_delay
        for attempt in range(attempts):
            conflict_token: Token[bool] = self._resource_lock_conflict.set(False)
            try:
                return super().http_request(
                    verb,
                    path,
                    query_data=query_data,
                    post_data=post_data,
                    raw=raw,
                    streamed=streamed,
                    files=files,
                    timeout=request_timeout,
                    # SDK header-driven sleeps are outside its socket timeout.
                    max_retries=0,
                    obey_rate_limit=False,
                    retry_transient_errors=False,
                    extra_headers=extra_headers,
                    **kwargs,
                )
            except GitlabHttpError as error:
                retryable: bool = (
                    error.response_code == HTTPStatus.TOO_MANY_REQUESTS
                    and obey_rate_limit
                ) or (
                    retry_transient
                    and (
                        error.response_code in RETRYABLE_TRANSIENT_ERROR_CODES
                        or (
                            error.response_code == HTTPStatus.CONFLICT
                            and self._resource_lock_conflict.get()
                        )
                    )
                )
                if not retryable or attempt + 1 == attempts:
                    raise
                failure: str = f"HTTP {error.response_code}"
            except (RequestsConnectionError, ChunkedEncodingError, Timeout) as error:
                if not retry_transient or attempt + 1 == attempts:
                    raise
                failure = type(error).__name__
            finally:
                self._resource_lock_conflict.reset(conflict_token)
            # Do not log URLs, headers, tokens, or remote response bodies.
            logger.warning(
                "GitLab %s attempt %d/%d failed (%s); retrying in %.1fs",
                verb,
                attempt + 1,
                attempts,
                failure,
                delay,
            )
            time.sleep(delay)
            delay = min(delay * 2, self._max_delay)
        raise RuntimeError("GitLab retry budget exhausted")
