#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path

from django.core.exceptions import ValidationError
from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response

from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.permissions import UserHasWriteAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.serializers import UploadSerializer
from speleodb.surveys.models import Permission
from speleodb.surveys.models import Project
from speleodb.utils.exceptions import NotAuthorizedError
from speleodb.utils.exceptions import ProjectNotFound
from speleodb.utils.exceptions import ResourceBusyError
from speleodb.utils.gitlab_manager import GitlabManager
from speleodb.utils.response import DownloadTMLResponseFromFile
from speleodb.utils.view_cls import CustomAPIView


class ProjectAcquireApiView(CustomAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasWriteAccess]
    serializer_class = ProjectSerializer
    http_method_names = ["post"]
    lookup_field = "id"

    def _post(self, request, *args, **kwargs):
        project = self.get_object()

        try:
            project.acquire_mutex(user=request.user)

        except ValidationError as e:
            raise ResourceBusyError(e.message) from None

        except PermissionError as e:
            raise NotAuthorizedError(e) from None

        try:
            serializer = ProjectSerializer(project, context={"user": request.user})
        except Exception:
            project.release_mutex(user=request.user)
            raise

        return serializer.data


class ProjectReleaseApiView(CustomAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasWriteAccess]
    serializer_class = ProjectSerializer
    http_method_names = ["post"]
    lookup_field = "id"

    def _post(self, request, *args, **kwargs):
        project = self.get_object()
        try:
            project.release_mutex(user=request.user)

        except ValidationError as e:
            raise ResourceBusyError(e.message) from None

        except PermissionError as e:
            raise NotAuthorizedError(e) from None

        try:
            serializer = ProjectSerializer(project, context={"user": request.user})
        except Exception:
            project.acquire_mutex(user=request.user)
            raise

        return serializer.data


class ProjectApiView(CustomAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasReadAccess]
    serializer_class = ProjectSerializer
    http_method_names = ["get"]
    lookup_field = "id"

    def _get(self, request, *args, **kwargs):
        project = self.get_object()
        serializer = ProjectSerializer(project, context={"user": request.user})

        return {
            "project": serializer.data,
            "history": GitlabManager.get_commit_history(project_id=project.id),
        }


class CreateProjectApiView(CustomAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    http_method_names = ["post"]

    def _post(self, request, *args, **kwargs):
        """
        Create the Todo with given todo data
        """
        serializer = ProjectSerializer(
            data=request.data, context={"user": request.user}
        )
        if serializer.is_valid():
            proj = serializer.save()
            Permission.objects.create(
                project=proj, user=request.user, level=Permission.Level.OWNER
            )

            return Response({"data": serializer.data}, status=status.HTTP_201_CREATED)

        return Response(
            {"errror": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class ProjectListApiView(CustomAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    http_method_names = ["get"]

    def _get(self, request, *args, **kwargs):
        usr_projects = [perm.project for perm in request.user.rel_permissions.all()]

        usr_projects = sorted(
            usr_projects, key=lambda proj: proj.modified_date, reverse=True
        )

        serializer = ProjectSerializer(
            usr_projects, many=True, context={"user": request.user}
        )

        return serializer.data


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

        # if artifact is None:
        #     data = {"error": (f"Project")}
        #     return Response(data, status=status.HTTP_404_NOT_FOUND)

        return DownloadTMLResponseFromFile(filepath=artifact, attachment=False)
