#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path

from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response

from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.permissions import UserHasWriteAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.serializers import UploadSerializer
from speleodb.surveys.models import Project
from speleodb.utils.exceptions import ProjectNotFound
from speleodb.utils.response import DownloadTMLResponseFromFile
from speleodb.utils.view_cls import CustomAPIView


class FileUploadView(CustomAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasWriteAccess]
    serializer_class = ProjectSerializer
    http_method_names = ["put"]
    lookup_field = "id"

    def _put(self, request, *args, **kwargs):
        project = self.get_object()

        commit_message = request.data.get("message", None)
        if commit_message is None or commit_message == "":
            data = {"error": (f"Empty or no `message` received: `{commit_message}`.")}
            return Response(data, status=status.HTTP_400_BAD_REQUEST)

        file_uploaded = request.data["artifact"]

        content_type = file_uploaded.content_type

        if content_type not in ["application/octet-stream", "application/zip"]:
            data = {
                "error": (
                    f"Unknown MIME Type received: `{content_type}`. "
                    "Expected: `application/octet-stream` or `application/zip`."
                )
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)

        f_extension = Path(file_uploaded.name).suffix.lower()
        if f_extension != ".tml":
            data = {
                "error": (
                    f"Unknown file extension received: `{f_extension}`. "
                    "Expected: `.tml`."
                )
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)

        commit_sha1 = project.process_uploaded_file(
            file=file_uploaded, user=request.user, commit_msg=commit_message
        )

        return {
            "content_type": content_type,
            "message": commit_message,
            "commit_sha1": commit_sha1,
            "project": ProjectSerializer(project, context={"user": request.user}).data,
        }


class FileDownloadView(CustomAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasReadAccess]
    serializer_class = UploadSerializer
    http_method_names = ["get"]
    lookup_field = "id"

    def get(self, request, commit_sha1=None, *args, **kwargs):
        project = self.get_object()
        try:
            artifact = project.generate_tml_file(commit_sha1=commit_sha1)
        except ProjectNotFound as e:
            data = {"error": str(e)}
            return Response(data, status=status.HTTP_404_NOT_FOUND)

        return DownloadTMLResponseFromFile(filepath=artifact, attachment=False)
