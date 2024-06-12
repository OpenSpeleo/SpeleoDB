#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path

from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response

from django.core.exceptions import ValidationError

from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.permissions import UserHasWriteAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.serializers import UploadSerializer
from speleodb.surveys.models import Project
from speleodb.utils.exceptions import ProjectNotFound
from speleodb.utils.response import DownloadResponseFromFile
from speleodb.utils.view_cls import CustomAPIView

from speleodb.processors.auto_selector import AutoSelectorUploadFileProcessor
from speleodb.processors.auto_selector import AutoSelectorDownloadFileProcessor


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

        try:
            file_uploaded = request.data["artifact"]
        except KeyError:
            return Response(
                {"error": "Uploaded file `artifact is missing.`"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            processor = AutoSelectorUploadFileProcessor(file=file_uploaded)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        commit_sha1 = processor.commit_uploaded_file(
            user=request.user,
            project=project,
            commit_msg=commit_message
        )

        # Refresh the `modified_date` field
        project.save()

        return {
            "content_type": processor.content_type,
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
            artifact = AutoSelectorDownloadFileProcessor(
                project=project,
                commit_sha1=commit_sha1
            )
        except ProjectNotFound as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

        return DownloadResponseFromFile(filepath=artifact, attachment=False)
