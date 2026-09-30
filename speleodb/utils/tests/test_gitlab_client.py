"""Redirect-target policy; live lifecycle tests exercise actual GitLab redirects."""

from __future__ import annotations

from http import HTTPStatus
from uuid import uuid4

import pytest
from requests import Request
from requests import Response

from speleodb.utils.gitlab_client import BoundedGitlabClient


@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize("keep_base_url", [True, False])
@pytest.mark.parametrize(
    ("base_url", "location", "preserved_location"),
    [
        (
            "http://gitlab:9080",
            "http://localhost:9080/api/v4/projects/6?statistics=true#details",
            "http://gitlab:9080/api/v4/projects/6?statistics=true#details",
        ),
        (
            "http://gitlab:9080/",
            "//localhost:9080/api/v4/projects/6",
            "http://gitlab:9080/api/v4/projects/6",
        ),
        (
            "https://internal.example/gitlab",
            "https://public.example/gitlab/api/v4/projects/6",
            "https://internal.example/gitlab/api/v4/projects/6",
        ),
        (
            "http://gitlab:9080",
            "/api/v4/projects/6",
            "/api/v4/projects/6",
        ),
        ("http://gitlab:9080", "6?statistics=true", "6?statistics=true"),
        (
            "http://gitlab:9080",
            "https://storage.example/archive.zip?signature=value",
            "https://storage.example/archive.zip?signature=value",
        ),
        (
            "http://gitlab:9080",
            "http://localhost:9080/users/sign_in",
            "http://localhost:9080/users/sign_in",
        ),
        (
            "http://gitlab:9080",
            "ftp://localhost:9080/api/v4/projects/6",
            "ftp://localhost:9080/api/v4/projects/6",
        ),
        (
            "https://internal.example/gitlab",
            "https://public.example/other/api/v4/projects/6",
            "https://public.example/other/api/v4/projects/6",
        ),
    ],
)
def test_keep_base_url_scopes_read_redirects_to_gitlab_api(
    method: str,
    *,
    keep_base_url: bool,
    base_url: str,
    location: str,
    preserved_location: str,
) -> None:
    client: BoundedGitlabClient = BoundedGitlabClient(
        base_url, private_token=f"unused-{uuid4()}", keep_base_url=keep_base_url
    )
    response: Response = Response()
    response.status_code = HTTPStatus.MOVED_PERMANENTLY
    response.headers["Location"] = location
    response.request = Request(method, f"{base_url}/api/v4/projects/old").prepare()
    try:
        assert client.session.get_redirect_target(response) == (
            preserved_location if keep_base_url else location
        )
        # Diagnostic hooks and SDK history retain the server's original header.
        assert response.headers["Location"] == location
    finally:
        client.session.close()


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_keep_base_url_preserves_write_redirect_handling(method: str) -> None:
    client: BoundedGitlabClient = BoundedGitlabClient(
        "http://gitlab:9080", private_token=f"unused-{uuid4()}", keep_base_url=True
    )
    location: str = "http://localhost:9080/api/v4/projects/6"
    response: Response = Response()
    response.status_code = HTTPStatus.MOVED_PERMANENTLY
    response.headers["Location"] = location
    response.request = Request(
        method, "http://gitlab:9080/api/v4/projects/old"
    ).prepare()
    try:
        assert client.session.get_redirect_target(response) == location
    finally:
        client.session.close()


def test_keep_base_url_does_not_redirect_successful_responses() -> None:
    client: BoundedGitlabClient = BoundedGitlabClient(
        "http://gitlab:9080", private_token=f"unused-{uuid4()}", keep_base_url=True
    )
    response: Response = Response()
    response.status_code = HTTPStatus.OK
    response.headers["Location"] = "http://localhost:9080/api/v4/projects/6"
    try:
        assert client.session.get_redirect_target(response) is None
    finally:
        client.session.close()
