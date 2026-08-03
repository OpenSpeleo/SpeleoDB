# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import TYPE_CHECKING
from typing import Any

import requests
from django.conf import settings
from django.http import HttpResponse
from django.http import StreamingHttpResponse
from requests.exceptions import RequestException
from requests.exceptions import Timeout
from rest_framework import status
from rest_framework.authentication import BasicAuthentication
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.renderers import BaseRenderer

from speleodb.api.v2.authentication import BearerAuthentication
from speleodb.api.v2.authentication import GitOAuth2Authentication
from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.permissions import SDB_WriteAccess
from speleodb.api.v2.serializers import ProjectSerializer
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import Project

if TYPE_CHECKING:
    from collections.abc import Generator
    from collections.abc import Iterator

    from django.http.response import HttpResponseBase
    from rest_framework.request import Request


logger = logging.getLogger(__name__)


UPSTREAM_REQUEST_HEADERS = (
    "Accept",
    "Cache-Control",
    "Content-Type",
    "Git-Protocol",
    "Pragma",
    "User-Agent",
)
UPSTREAM_RESPONSE_HEADERS = ("Cache-Control", "Expires", "Pragma")
UPSTREAM_ERROR_MESSAGE = "SpeleoDB Git service is temporarily unavailable."


class GitService(Enum):
    RECEIVE = "git-receive-pack"
    UPLOAD = "git-upload-pack"


class UpstreamResponseStream:
    """Stream and close a Git upstream response without changing its bytes."""

    def __init__(
        self,
        response: requests.Response,
        *,
        project_id: str,
        request_method: str,
        service: GitService,
    ) -> None:
        self.response = response
        self.project_id = project_id
        self.request_method = request_method
        self.service = service
        self.is_closed = False

    def __iter__(self) -> Iterator[bytes]:
        try:
            yield from self.response.iter_content(chunk_size=8192)
        except RequestException:
            logger.exception(
                "Git upstream stream failed: project_id=%s method=%s service=%s",
                self.project_id,
                self.request_method,
                self.service.value,
            )
            raise
        finally:
            self.close()

    def close(self) -> None:
        if self.is_closed:
            return
        self.is_closed = True
        self.response.close()


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


def generate_upstream_error_response() -> HttpResponse:
    """Return a stable response without exposing an upstream error document."""
    return HttpResponse(
        UPSTREAM_ERROR_MESSAGE,
        status=status.HTTP_502_BAD_GATEWAY,
        content_type="text/plain",
        headers={"Cache-Control": "no-store"},
    )


def normalize_media_type(content_type: str | None) -> str:
    """Normalize an HTTP Content-Type value for exact media-type comparison."""
    return (content_type or "").partition(";")[0].strip().lower()


def get_expected_media_type(service: GitService, *, discovery: bool) -> str:
    response_kind = "advertisement" if discovery else "result"
    return f"application/x-{service.value}-{response_kind}"


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
    schema = None
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
        self,
        request: Request,
        service: GitService,
        *,
        discovery: bool = False,
        query_params: dict[str, Any] | None = None,
    ) -> HttpResponseBase:
        project = self.get_object()
        (_old_hash, _), branch_name = parse_git_push_preamble(request.body)

        if branch_name is not None and branch_name != settings.DJANGO_GIT_BRANCH_NAME:
            return generate_git_error_response(
                f"Only commits on branch `{settings.DJANGO_GIT_BRANCH_NAME}` are "
                "allowed.",
                service_name=service.value,
            )

        # if old_hash is not None and all(char == "0" for char in old_hash):
        #     return generate_git_error_response(
        #         "Force push commits are not allowed - please rebase on `master`",
        #         service_name=service.value,
        #     )

        path = "info/refs" if discovery else service.value
        target_url = f"{settings.GITLAB_HTTP_PROTOCOL}://{self.git_creds.instance}/{self.git_creds.group_name}/{project.id}.git/{path}"
        headers = {
            header: request.headers[header]
            for header in UPSTREAM_REQUEST_HEADERS
            if header in request.headers
        }
        headers["Accept-Encoding"] = "identity"
        request_method = request.method or "GET"
        data = None if request_method == "GET" else request.body

        gitlab_response: requests.Response
        for tentative_id in range(2):
            try:
                gitlab_response = requests.api.request(
                    method=request_method,
                    url=target_url,
                    headers=headers,
                    data=data,
                    params=query_params,
                    auth=("oauth2", self.git_creds.token),
                    allow_redirects=False,
                    stream=True,
                    timeout=30,
                )
            except Timeout:
                logger.warning(
                    "Git upstream request timed out: project_id=%s method=%s "
                    "service=%s",
                    project.id,
                    request_method,
                    service.value,
                )
                return generate_upstream_error_response()
            except RequestException:
                logger.exception(
                    "Git upstream request failed: project_id=%s method=%s service=%s",
                    project.id,
                    request_method,
                    service.value,
                )
                return generate_upstream_error_response()

            if gitlab_response.status_code != status.HTTP_404_NOT_FOUND:
                break

            if tentative_id == 0:
                gitlab_response.close()
                try:
                    GitlabManager.create_or_clone_project(project)
                except Exception:  # noqa: BLE001
                    # Recovery spans GitLab API and Git subprocess exception types.
                    # Exception text may contain the credential-bearing clone URL.
                    logger.warning(
                        "Git upstream repository recovery failed: project_id=%s "
                        "method=%s service=%s",
                        project.id,
                        request_method,
                        service.value,
                    )
                    return generate_upstream_error_response()
        else:
            return self.reject_upstream_response(
                gitlab_response,
                project_id=str(project.id),
                request_method=request_method,
                service=service,
            )

        expected_media_type = get_expected_media_type(
            service,
            discovery=discovery,
        )
        if (
            gitlab_response.status_code != status.HTTP_200_OK
            or normalize_media_type(gitlab_response.headers.get("Content-Type"))
            != expected_media_type
        ):
            return self.reject_upstream_response(
                gitlab_response,
                project_id=str(project.id),
                request_method=request_method,
                service=service,
            )

        django_response = StreamingHttpResponse(
            UpstreamResponseStream(
                gitlab_response,
                project_id=str(project.id),
                request_method=request_method,
                service=service,
            ),
            status=gitlab_response.status_code,
            content_type=gitlab_response.headers.get("Content-Type"),
            reason=gitlab_response.reason,
        )

        for header in UPSTREAM_RESPONSE_HEADERS:
            if (value := gitlab_response.headers.get(header)) is not None:
                django_response[header] = value

        return django_response

    def reject_upstream_response(
        self,
        gitlab_response: requests.Response,
        *,
        project_id: str,
        request_method: str,
        service: GitService,
    ) -> HttpResponse:
        upstream_content_type = normalize_media_type(
            gitlab_response.headers.get("Content-Type")
        )
        upstream_request_id = gitlab_response.headers.get("X-Request-Id", "")
        try:
            logger.error(
                "Git upstream response rejected: project_id=%s method=%s service=%s "
                "status=%s content_type=%s request_id=%s",
                project_id,
                request_method,
                service.value,
                gitlab_response.status_code,
                upstream_content_type,
                upstream_request_id,
            )
        finally:
            gitlab_response.close()

        return generate_upstream_error_response()


class InfoRefsView(BaseGitProxyAPIView):
    permission_classes = [SDB_ReadAccess]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> HttpResponseBase:
        git_service = request.query_params.get("service")

        if git_service is None or git_service not in [s.value for s in GitService]:
            return generate_git_error_response(
                f"Invalid service: `{git_service}`. "
                f"Expected: {[s.value for s in GitService]}.",
                service_name=str(git_service),
            )

        return self.proxy_git_request(
            request,
            service=GitService(git_service),
            discovery=True,
            query_params=request.query_params,
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
    permission_classes = [SDB_ReadAccess]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> HttpResponseBase:
        return self.proxy_git_request(request, service=GitService.UPLOAD)


class WriteServiceView(RWServiceView):
    permission_classes = [SDB_WriteAccess]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> HttpResponseBase:
        git_service = GitService.RECEIVE

        # Check for active mutex
        if (
            mutex := self.get_object().active_mutex
        ) is None or mutex.user != request.user:
            return generate_git_error_response(
                "You did not lock the project - Impossible to push",
                service_name=git_service.value,
            )

        # TODO: Add the creation of `ProjectCommit` objects after a successful push

        return self.proxy_git_request(request, service=git_service)
