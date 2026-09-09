from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import override

import gitlab
from django.conf import settings

if TYPE_CHECKING:
    from typing import BinaryIO

    from requests import Response


class GitlabClient(gitlab.Gitlab):
    """A finite request budget, including paginated and authentication reads."""

    def __init__(
        self, url: str, *, private_token: str, keep_base_url: bool = False
    ) -> None:
        super().__init__(
            url,
            private_token=private_token,
            keep_base_url=keep_base_url,
            timeout=30,
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
        return super().http_request(
            verb,
            path,
            query_data=query_data,
            post_data=post_data,
            raw=raw,
            streamed=streamed,
            files=files,
            timeout=timeout,
            obey_rate_limit=obey_rate_limit,
            retry_transient_errors=(
                verb.upper() in {"GET", "HEAD"}
                if retry_transient_errors is None
                else retry_transient_errors
            ),
            max_retries=(
                settings.DJANGO_GIT_RETRY_ATTEMPTS - 1
                if max_retries is None
                else max_retries
            ),
            extra_headers=extra_headers,
            **kwargs,
        )
