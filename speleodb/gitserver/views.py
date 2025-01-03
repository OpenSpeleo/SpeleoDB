from enum import Enum

import requests
from django.http import JsonResponse
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
from speleodb.api.v1.permissions import UserHasReadAccess
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
    format = "api"


class BaseGitProxyAPIView(GenericAPIView):
    """
    A DRF view that proxies Git commands (e.g., clone, push, pull) to GitLab.
    """

    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    authentication_classes = [
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

            # Construct the target GitLab URL
            target_url = f"https://oauth2:{self._gitlab_token}@{self._gitlab_instance}/{self._gitlab_group_name}/{project.id}.git/{path}"

            # Forward the request using requests with streaming
            headers = dict(request.headers.copy())
            headers.pop("Host", None)  # Avoid passing Host header

            # Add Accept-Encoding: identity to prevent automatic content decoding
            headers["Accept-Encoding"] = "identity"

            # Forward the request using httpx
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
                        "accept-ranges",
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
    def get(self, request, command: str, *args, **kwargs):
        """
        Handles Git clone commands (GET for fetch).
        """
        service = request.query_params.get("service")
        if service not in [s.value for s in GitService]:
            return JsonResponse(
                {"error": "Invalid service"}, status=status.HTTP_400_BAD_REQUEST
            )

        return self.proxy_git_request(
            request, path=f"info/{command}", query_params=request.query_params
        )


class ServiceView(BaseGitProxyAPIView):
    # Necessary to accept the custom media-types from Git
    renderer_classes = [AcceptEverythingRenderer]

    def post(self, request, service: str, *args, **kwargs):
        """
        Handles Git commands (POST for push/pull).
        """
        if service not in [s.value for s in GitService]:
            return JsonResponse(
                {"error": "Invalid service"}, status=status.HTTP_400_BAD_REQUEST
            )
        return self.proxy_git_request(request, path=service)
