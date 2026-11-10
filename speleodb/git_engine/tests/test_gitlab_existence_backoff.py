"""Reject invalid not-found retry policy before making an SDK request."""

from __future__ import annotations

from uuid import uuid4

import pytest

from speleodb.utils.gitlab_client import BoundedGitlabClient


@pytest.mark.parametrize("verb", ["POST", "PUT", "PATCH", "DELETE"])
def test_missing_retry_rejected_for_writes(verb: str) -> None:
    with (
        BoundedGitlabClient("http://127.0.0.1:1", private_token=uuid4().hex) as client,
        pytest.raises(ValueError, match="GET/HEAD"),
    ):
        client.http_request(verb, "/projects/example", retry_not_found=True)
