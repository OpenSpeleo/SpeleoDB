#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path

from django.core.exceptions import ValidationError
from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response

from speleodb.surveys.api.v1.exceptions import NotAuthorizedError
from speleodb.surveys.api.v1.exceptions import ResourceBusyError
from speleodb.surveys.api.v1.permissions import UserHasReadAccess
from speleodb.surveys.api.v1.permissions import UserHasWriteAccess
from speleodb.surveys.api.v1.serializers import ProjectSerializer
from speleodb.surveys.api.v1.serializers import UploadSerializer
from speleodb.surveys.models import Permission
from speleodb.surveys.models import Project
from speleodb.utils.response import DownloadResponseFromFile
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

        return serializer.data


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
        project = self.get_object()  # noqa: F841
        file_uploaded = request.FILES.get("file_uploaded")
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
        # file_uploaded =>
        # {
        #     "_name": "test_simple.tml",
        #     "charset": None,
        #     "content_type": "application/octet-stream",
        #     "content_type_extra": {},
        #     "field_name": "file_uploaded",
        #     "file": <_io.BytesIO object at 0x71e8c6b982c0>,
        #     "size": 92424
        # }
        return {
            "message": f"PUT API and you have uploaded a {content_type} file",
            "project": ProjectSerializer(project, context={"user": request.user}).data,
        }


class FileDownloadView(CustomAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasReadAccess]
    serializer_class = UploadSerializer
    http_method_names = ["get"]
    lookup_field = "id"

    def get(self, request, commit_sha1=None, *args, **kwargs):
        if commit_sha1 is None:
            # pull ToT
            pass
        project = self.get_object()  # noqa: F841
        return DownloadResponseFromFile(
            filepath="fixtures/test_simple.tml", attachment=False
        )
