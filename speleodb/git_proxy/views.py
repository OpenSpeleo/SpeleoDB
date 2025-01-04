import re
from enum import Enum

import requests
from django.conf import settings
from django.http import HttpResponseNotAllowed
from django.http import StreamingHttpResponse
from requests.exceptions import RequestException
from requests.exceptions import Timeout
from rest_framework import status
from rest_framework.authentication import BasicAuthentication
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import GenericAPIView
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response

from speleodb.api.v1.authentication import BearerAuthentication
from speleodb.api.v1.authentication import GitOAuth2Authentication
from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.permissions import UserHasWriteAccess
from speleodb.api.v1.permissions import UserOwnsProjectMutex
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.common.models import Option
from speleodb.surveys.models import Project
from speleodb.utils.lazy_string import LazyString


class GitService(Enum):
    RECEIVE = "git-receive-pack"
    UPLOAD = "git-upload-pack"


class AcceptEverythingRenderer(BaseRenderer):
    """
    A renderer that accepts everything and does not process anything
    """

    media_type = "*/*"
    format = "text"
    charset = "iso-8859-1"

    def render(self, data, media_type=None, renderer_context=None):
        return data.encode(self.charset)


def parse_git_push_preamble(payload: bytes):
    """
    Parse the Git push preamble to extract branch name and check if it's a force push.
    Returns a tuple (branch_name, is_force_push).
    """
    # Decode the payload until the binary packfile starts
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


class BaseGitProxyAPIView(GenericAPIView):
    """
    A DRF view that proxies Git commands (e.g., clone, push, pull) to GitLab.
    """

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    lookup_field = "id"

    authentication_classes = [
        GitOAuth2Authentication,
        BasicAuthentication,
        TokenAuthentication,
        BearerAuthentication,
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._gitlab_instance = LazyString(
            lambda: Option.get_or_empty(name="GITLAB_HOST_URL")
        )
        self._gitlab_token = LazyString(
            lambda: Option.get_or_empty(name="GITLAB_TOKEN")
        )
        self._gitlab_group_name = LazyString(
            lambda: Option.get_or_empty(name="GITLAB_GROUP_NAME")
        )

    def proxy_git_request(self, request, path: str, query_params: dict | None = None):
        """
        Forward the request to GitLab and return the response to the client.
        """
        try:
            project: Project = self.get_object()

            (old_hash, _), branch_name = parse_git_push_preamble(request.body)

            if (
                branch_name is not None
                and branch_name != settings.DJANGO_GIT_BRANCH_NAME
            ):
                return HttpResponseNotAllowed(
                    f"Only commits on {settings.DJANGO_GIT_BRANCH_NAME} are allowed.",
                    content_type="text/plain",
                )

            if old_hash is not None and all(char == "0" for char in old_hash):
                return HttpResponseNotAllowed(
                    "Force push commits are not allowed.", content_type="text/plain"
                )

            # Construct the target GitLab URL
            target_url = f"https://oauth2:{self._gitlab_token}@{self._gitlab_instance}/{self._gitlab_group_name}/{project.id}.git/{path}"

            # Forward the request using requests with streaming
            headers = dict(request.headers.copy())
            headers.pop("Host", None)  # Avoid passing Host header

            # Add Accept-Encoding: identity to prevent automatic content decoding
            headers["Accept-Encoding"] = "identity"

            # Forward the request using `requests`
            gitlab_response = requests.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=request.body,
                params=query_params,
                stream=True,  # Enable streaming for the response
                timeout=30,
            )

            # Prepare the streaming response
            django_response = StreamingHttpResponse(
                gitlab_response.raw,  # Stream raw response content
                status=gitlab_response.status_code,
            )

            # Copy essential headers
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
            return Response(
                {"error": "Request timed out. Try again later."},
                status=status.HTTP_408_REQUEST_TIMEOUT,
            )

        except RequestException as e:
            return Response(
                {"error": f"RPC failed: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class InfoRefsView(BaseGitProxyAPIView):
    permission_classes = [UserHasReadAccess]

    def get(self, request, command: str, *args, **kwargs):
        """
        Handles Git clone commands (GET for fetch).
        """
        service = request.query_params.get("service")
        if service not in [s.value for s in GitService]:
            return HttpResponseNotAllowed(
                f"Invalid service: `{service}`. "
                f"Expected: {[s.value for s in GitService]}.",
                content_type="text/plain",
            )

        return self.proxy_git_request(
            request, path=f"info/{command}", query_params=request.query_params
        )


class ReadServiceView(BaseGitProxyAPIView):
    permission_classes = [UserHasReadAccess]

    # Necessary to accept the custom media-types from Git
    renderer_classes = [AcceptEverythingRenderer]

    def post(self, request, *args, **kwargs):
        """
        Handles Git commands (POST for push/pull).
        """
        return self.proxy_git_request(request, path="git-upload-pack")


class WriteServiceView(BaseGitProxyAPIView):
    permission_classes = [UserHasWriteAccess, UserOwnsProjectMutex]

    # Necessary to accept the custom media-types from Git
    renderer_classes = [AcceptEverythingRenderer]

    def post(self, request, *args, **kwargs):
        """
        Handles Git commands (POST for push/pull).
        """
        return self.proxy_git_request(request, path="git-receive-pack")
