#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path

from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response

from speleodb.surveys.api.v1.exceptions import NotAuthorizedError
from speleodb.surveys.api.v1.exceptions import ResourceBusyError
from speleodb.surveys.api.v1.serializers import ProjectSerializer
from speleodb.surveys.api.v1.serializers import UploadSerializer
from speleodb.surveys.api.v1.view_cls import CustomAPIView
from speleodb.surveys.models import Permission
from speleodb.surveys.models import Project


class ProjectAcquireApiView(CustomAPIView):
    # add permission to check if user is authenticated
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    http_method_names = ["post"]

    def _post(self, request, project_id):
        project = Project.objects.get(id=project_id)

        if not project.has_write_access(user=request.user):
            raise NotAuthorizedError(
                f"User: `{request.user.email} can not execute this action.`"
            )
        try:
            project.acquire_mutex(user=request.user)

        except ValidationError as e:
            raise ResourceBusyError(e.message) from None

        except PermissionError as e:
            raise NotAuthorizedError(e) from None

        try:
            serializer = ProjectSerializer(project)
            proj_dict = serializer.data
            proj_dict["permission"] = project.get_permission(
                user=request.user
            ).level_name
        except Exception:
            project.release_mutex(user=request.user)
            raise

        return proj_dict


class ProjectReleaseApiView(CustomAPIView):
    # add permission to check if user is authenticated
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    http_method_names = ["post"]

    def _post(self, request, project_id):
        project = Project.objects.get(id=project_id)

        if not project.has_write_access(user=request.user):
            raise NotAuthorizedError(
                f"User: `{request.user.email} can not execute this action.`"
            )
        try:
            project.release_mutex(user=request.user)

        except ValidationError as e:
            raise ResourceBusyError(e.message) from None

        except PermissionError as e:
            raise NotAuthorizedError(e) from None

        try:
            serializer = ProjectSerializer(project)
            proj_dict = serializer.data
            proj_dict["permission"] = project.get_permission(
                user=request.user
            ).level_name
        except Exception:
            project.acquire_mutex(user=request.user)
            raise

        return proj_dict


class ProjectApiView(CustomAPIView):
    # add permission to check if user is authenticated
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    http_method_names = ["get"]

    def _get(self, request, project_id):
        project = Project.objects.get(id=project_id)
        serializer = ProjectSerializer(project)
        proj_dict = serializer.data
        proj_dict["permission"] = project.get_permission(user=request.user).level_name

        return proj_dict


class CreateProjectApiView(CustomAPIView):
    # add permission to check if user is authenticated
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    http_method_names = ["post"]

    def _post(self, request):
        """
        Create the Todo with given todo data
        """
        serializer = ProjectSerializer(data=request.data)
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
    # add permission to check if user is authenticated
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    http_method_names = ["get"]

    def _get(self, request):
        usr_projects = [
            (perm.project, perm.level_name)
            for perm in request.user.rel_permissions.all()
        ]

        usr_projects = sorted(
            usr_projects, key=lambda proj: proj[0].modified_date, reverse=True
        )

        projects, levels = zip(*usr_projects, strict=False)
        serializer = ProjectSerializer(projects, many=True)

        results = []
        for proj_dict, level in zip(serializer.data, levels, strict=False):
            proj_dict["permission"] = level
            results.append(proj_dict)

        return results


class FileUploadView(CustomAPIView):
    # add permission to check if user is authenticated
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UploadSerializer
    http_method_names = ["put"]

    def _put(self, request, project_id):
        file_uploaded = request.FILES.get("file_uploaded")
        content_type = file_uploaded.content_type

        if content_type != "application/octet-stream":
            data = {
                "error": (
                    f"Unknown MIME Type received: `{content_type}`. "
                    "Expected: `application/octet-stream`."
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
        #     '_name': 'test_simple.tml',
        #     'charset': None,
        #     'content_type': 'application/octet-stream',
        #     'content_type_extra': {},
        #     'field_name': 'file_uploaded',
        #     'file': <_io.BytesIO object at 0x71e8c6b982c0>,
        #     'size': 92424
        # }
        return {
            "data": f"PUT API and you have uploaded a {content_type} file",
            "project_id": project_id,
        }
