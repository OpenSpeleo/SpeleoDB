from __future__ import annotations

from django.conf import settings

from speleodb.utils.gitlab_client import BoundedGitlabClient


class GitlabClient(BoundedGitlabClient):
    """Application settings for the shared bounded GitLab transport."""

    def __init__(
        self, url: str, *, private_token: str, keep_base_url: bool = False
    ) -> None:
        super().__init__(
            url,
            private_token=private_token,
            keep_base_url=keep_base_url,
            max_attempts=settings.DJANGO_GIT_RETRY_ATTEMPTS,
            timeout=settings.DJANGO_GITLAB_HTTP_TIMEOUT_SECONDS,
            base_delay=settings.DJANGO_GIT_RETRY_BASE_DELAY_SECONDS,
            max_delay=settings.DJANGO_GIT_RETRY_MAX_DELAY_SECONDS,
        )
