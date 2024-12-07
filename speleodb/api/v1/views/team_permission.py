#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from speleodb.api.v1.permissions import UserHasAdminAccess
from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.serializers import TeamPermissionListSerializer
from speleodb.api.v1.serializers import TeamPermissionSerializer
from speleodb.surveys.models import Project
from speleodb.surveys.models import TeamPermission
from speleodb.users.models import SurveyTeam
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse


class ProjectTeamPermissionListView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        project: Project = self.get_object()
        permissions = project.get_all_team_permissions()

        project_serializer = ProjectSerializer(project, context={"user": request.user})
        permission_serializer = TeamPermissionListSerializer(permissions)

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permissions": permission_serializer.data,
            }
        )


class ProjectTeamPermissionView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasAdminAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def _process_request_data(self, data, skip_level=False):
        perm_data = {}
        for key in ["team", "level"]:
            try:
                if key == "level" and skip_level:
                    continue

                value = data[key]

                if key == "level":
                    if not isinstance(value, str) or value.upper() not in [
                        name for _, name in TeamPermission.Level.choices
                    ]:
                        return ErrorResponse(
                            {"error": f"Invalid value received for `{key}`: `{value}`"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    perm_data[key] = getattr(TeamPermission.Level, value.upper())

                elif key in "team":
                    try:
                        perm_data[key] = SurveyTeam.objects.get(id=value)
                    except ObjectDoesNotExist:
                        return ErrorResponse(
                            {"error": f"The team: `{value}` does not exist."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            except KeyError:
                return ErrorResponse(
                    {"error": f"Attribute: `{key}` is missing"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return perm_data

    def post(self, request, *args, **kwargs):
        project = self.get_object()

        perm_data = self._process_request_data(data=request.data)

        # An Error occured
        if isinstance(perm_data, Response):
            return perm_data

        permission, created = TeamPermission.objects.get_or_create(
            project=project, target=perm_data["team"]
        )

        if not created and permission.is_active:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this team: `{perm_data['team']}` "
                        "already exist."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        permission.reactivate(level=perm_data["level"])

        permission_serializer = TeamPermissionSerializer(permission)
        project_serializer = ProjectSerializer(project, context={"user": request.user})

        # Refresh the `modified_date` field
        project.save()

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, *args, **kwargs):
        project = self.get_object()

        perm_data = self._process_request_data(data=request.data)

        # An Error occured
        if isinstance(perm_data, Response):
            return perm_data

        try:
            permission = TeamPermission.objects.get(
                project=project, target=perm_data["team"]
            )
        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this team: `{perm_data['team']}` "
                        "does not exist."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not permission.is_active:
            return ErrorResponse(
                {
                    "error": (
                        f"The permission for this user: `{perm_data['user']}` "
                        "is inactive. Recreate the permission."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        permission.level = perm_data["level"]
        permission.save()

        permission_serializer = TeamPermissionSerializer(permission)
        project_serializer = ProjectSerializer(project, context={"user": request.user})

        # Refresh the `modified_date` field
        project.save()

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, *args, **kwargs):
        project = self.get_object()

        perm_data = self._process_request_data(data=request.data, skip_level=True)

        # An Error occured
        if isinstance(perm_data, Response):
            return perm_data

        try:
            permission = TeamPermission.objects.get(
                project=project, target=perm_data["team"]
            )
        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this team: `{perm_data['team']}` "
                        "does not exist."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        permission.deactivate(deactivated_by=request.user)
        project_serializer = ProjectSerializer(project, context={"user": request.user})

        # Refresh the `modified_date` field
        project.save()

        return SuccessResponse(
            {
                "project": project_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )
