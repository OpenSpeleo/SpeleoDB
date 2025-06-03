# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from enum import Enum
from typing import TYPE_CHECKING
from typing import Any

import requests
from django.conf import settings
from django.http import StreamingHttpResponse
from requests.exceptions import RequestException
from requests.exceptions import Timeout
from rest_framework import status
from rest_framework.authentication import BasicAuthentication
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.renderers import BaseRenderer

from speleodb.api.v1.authentication import BearerAuthentication
from speleodb.api.v1.authentication import GitOAuth2Authentication
from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.permissions import UserHasWriteAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import Project

if TYPE_CHECKING:
    from collections.abc import Generator

    from rest_framework.request import Request


class GitService(Enum):
    RECEIVE = "git-receive-pack"
    UPLOAD = "git-upload-pack"


def format_packet_line(line: str) -> str:
    """
    Format a line as a Git packet line.
    """
    return f"{len(line) + 4:04x}{line}"


def generate_git_error_response(
    message: str, service_name: str
) -> StreamingHttpResponse:
    """
    Generate an error response that will be properly displayed by the git client.
    """
    # <len>\x02<ERROR MESSAGE>004a\x01000eunpack ok\n0033ng refs/heads/master pre-receive hook declined\n00000000  # noqa: E501
    # <len>\x02<ERROR MESSAGE>004a\x01000eunpack ok\n0033ng refs/heads/master pre-receive hook declined\n00000000  # noqa: E501
    packet_line = format_packet_line(f"\x02SpeleoDB: {message}.")
    packet_line += format_packet_line(
        "\x01000eunpack ok\n0033ng refs/heads/master pre-receive hook declined\n"
    )
    # Add a flush packet to indicate the end of the response
    packet_line += "00000000"

    def yield_from(iterable: list[Any]) -> Generator[Any]:
        yield from iterable

    return StreamingHttpResponse(
        yield_from([packet_line]),
        status=status.HTTP_200_OK,
        content_type=f"application/x-{service_name}-result",
        headers={"Cache-Control": "no-cache"},
    )


def parse_git_push_preamble(payload: bytes) -> Any:
    decoded_data = payload.decode(errors="ignore")
    old_hash = new_hash = branch_name = None
    match = re.search(
        r"([0-9a-f]{40}) ([0-9a-f]{40}) refs/heads/([\w\-_/]+)\x00", decoded_data
    )
    if match:
        old_hash = match.group(1)
        new_hash = match.group(2)
        branch_name = match.group(3)
    return (old_hash, new_hash), branch_name


class GitErrorRenderer(BaseRenderer):
    """
    Renderer to format error messages according to the Git protocol.
    """

    media_type = "*/*"
    format = "text"
    charset: str = "iso-8859-1"

    def render(
        self,
        data: Any,
        accepted_media_type: str | None = None,
        renderer_context: Any | None = None,
    ) -> Any:
        if isinstance(data, str):
            return data.encode(self.charset)
        return data


class BaseGitProxyAPIView(GenericAPIView[Project]):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    lookup_field = "id"
    renderer_classes = [GitErrorRenderer]

    authentication_classes = [
        GitOAuth2Authentication,
        BasicAuthentication,
        TokenAuthentication,
        BearerAuthentication,
    ]

    @property
    def git_creds(self) -> GitlabCredentials:
        return GitlabCredentials.get()

    def proxy_git_request(
        self, request: Request, path: str, query_params: dict[str, Any] | None = None
    ) -> StreamingHttpResponse:
        try:
            project = self.get_object()
            (old_hash, _), branch_name = parse_git_push_preamble(request.body)

            if (
                branch_name is not None
                and branch_name != settings.DJANGO_GIT_BRANCH_NAME
            ):
                return generate_git_error_response(
                    f"Only commits on branch `{settings.DJANGO_GIT_BRANCH_NAME}` are "
                    "allowed.",
                    service_name=path,
                )

            # if old_hash is not None and all(char == "0" for char in old_hash):
            #     return generate_git_error_response(
            #         "Force push commits are not allowed - please rebase on `master`",
            #         service_name=path,
            #     )

            target_url = f"https://oauth2:{self.git_creds.token}@{self.git_creds.instance}/{self.git_creds.group_name}/{project.id}.git/{path}"
            headers = dict(request.headers.copy())
            headers.pop("Host", None)
            headers["Accept-Encoding"] = "identity"

            for tentative_id in range(2):
                data = None if request.method == "GET" else request.body
                gitlab_response = requests.request(
                    method=request.method,  # type: ignore[arg-type]
                    url=target_url,
                    headers=headers,
                    data=data,
                    params=query_params,
                    stream=True,
                    timeout=30,
                )

                if gitlab_response.status_code != status.HTTP_404_NOT_FOUND:
                    break

                if tentative_id == 0:
                    GitlabManager.create_or_clone_project(project.id)
            else:
                return generate_git_error_response(
                    "Impossible to connect with Gitlab distant server.",
                    service_name=path,
                )

            def stream_response() -> Generator[Any]:
                for chunk in gitlab_response.iter_content(chunk_size=8192):
                    _chunk = chunk
                    if b"GitLab" in _chunk:
                        _chunk = _chunk.decode("iso-8859-1")
                        _chunk = _chunk.replace("GitLab", "SpeleoDB")
                        length = int(_chunk[:4], 16)
                        _chunk = f"{length + 2:04x}{_chunk[4:]}"
                        _chunk = _chunk.encode("iso-8859-1")
                    yield _chunk

            django_response = StreamingHttpResponse(
                stream_response(),
                status=gitlab_response.status_code,
                content_type=gitlab_response.headers.get("Content-Type"),
                reason=gitlab_response.reason,
            )

            for header, value in gitlab_response.headers.items():
                header_key = header.lower()
                if (
                    header_key
                    not in [
                        "connection",
                        "content-length",
                        "nel",
                        "report-to",
                        "set-cookie",
                        "server",
                        "transfer-encoding",
                        "x-content-type-options",
                    ]
                    and not header_key.startswith("gitlab")
                    and not header_key.startswith("cf-")
                ):
                    django_response[header] = value

            return django_response

        except Timeout:
            return generate_git_error_response(
                "Request timed out. Try again later.",
                service_name=path,
            )

        except RequestException as e:
            return generate_git_error_response(
                f"RPC failed: {e}",
                service_name=path,
            )

        except Exception as e:  # noqa: BLE001
            return generate_git_error_response(
                f"Unknown event happened - None response: {e}",
                service_name=path,
            )


class InfoRefsView(BaseGitProxyAPIView):
    permission_classes = [UserHasReadAccess]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> StreamingHttpResponse:
        git_service = request.query_params.get("service")

        if git_service is None or git_service not in [s.value for s in GitService]:
            return generate_git_error_response(
                f"Invalid service: `{git_service}`. "
                f"Expected: {[s.value for s in GitService]}.",
                service_name=str(git_service),
            )

        return self.proxy_git_request(
            request, path="info/refs", query_params=request.query_params
        )


class RWServiceView(BaseGitProxyAPIView):
    def handle_exception(self, exc: BaseException) -> StreamingHttpResponse:  # type: ignore[override]
        if isinstance(exc, PermissionDenied):
            return generate_git_error_response(
                "You do not have permission to access this resource.",
                service_name="git",
            )

        return generate_git_error_response(f"Exception: {exc}", service_name="git")


class ReadServiceView(RWServiceView):
    permission_classes = [UserHasReadAccess]

    def post(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> StreamingHttpResponse:
        git_service = "git-upload-pack"
        return self.proxy_git_request(request, path=git_service)


class WriteServiceView(RWServiceView):
    permission_classes = [UserHasWriteAccess]

    def post(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> StreamingHttpResponse:
        git_service = "git-receive-pack"

        # Check for active mutex
        if (
            mutex := self.get_object().active_mutex
        ) is None or mutex.user != request.user:
            return generate_git_error_response(
                "You did not lock the project - Impossible to push",
                service_name=git_service,
            )

        return self.proxy_git_request(request, path="git-receive-pack")
