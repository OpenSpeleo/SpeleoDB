#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import IsReadOnly
from speleodb.api.v1.permissions import UserHasAdminAccess
from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.serializers import SurveyTeamSerializer
from speleodb.api.v1.serializers import TeamPermissionListSerializer
from speleodb.api.v1.serializers import TeamPermissionSerializer
from speleodb.api.v1.serializers import TeamRequestSerializer
from speleodb.api.v1.serializers import TeamRequestWithProjectLevelSerializer
from speleodb.surveys.models import Project
from speleodb.surveys.models import TeamPermission
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse


class ProjectTeamPermissionListView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        project: Project = self.get_object()
        team_permissions = project.get_all_team_permissions()

        project_serializer = ProjectSerializer(project, context={"user": request.user})
        permission_serializer = TeamPermissionListSerializer(team_permissions)

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permissions": permission_serializer.data,
            }
        )


class ProjectTeamPermissionView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [UserHasAdminAccess | (IsReadOnly & UserHasReadAccess)]
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        project = self.get_object()

        serializer = TeamRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = serializer.validated_data["team"]

        try:
            permission = TeamPermission.objects.get(project=project, target=team)

        except ObjectDoesNotExist:
            return ErrorResponse(
                {"error": (f"A permission for this team: `{team}` does not exist.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        permission_serializer = TeamPermissionSerializer(permission)
        project_serializer = ProjectSerializer(project, context={"user": request.user})
        team_serializer = SurveyTeamSerializer(team, context={"user": request.user})

        return SuccessResponse(
            {
                "permission": permission_serializer.data,
                "project": project_serializer.data,
                "team": team_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        serializer = TeamRequestWithProjectLevelSerializer(
            data=request.data, context={"requesting_user": request.user}
        )

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = serializer.validated_data["team"]
        access_level = serializer.validated_data["level"]

        project = self.get_object()
        permission, created = TeamPermission.objects.get_or_create(
            project=project, target=team
        )

        if not created:
            if permission.is_active:
                return ErrorResponse(
                    {
                        "error": (
                            f"The permission for this team: `{team}` " "already exists."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Reactivate permission
            permission.reactivate(level=access_level)
            permission.save()

        else:
            # Now assign the role. Couldn't do it during object creation because
            # of the use of `get_or_create`
            permission.level = access_level
            permission.save()

        # Refresh the `modified_date` field
        project.save()

        permission_serializer = TeamPermissionSerializer(permission)
        project_serializer = ProjectSerializer(project, context={"user": request.user})

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, *args, **kwargs):
        serializer = TeamRequestWithProjectLevelSerializer(
            data=request.data, context={"requesting_user": request.user}
        )

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = serializer.validated_data["team"]
        access_level = serializer.validated_data["level"]

        project = self.get_object()
        try:
            permission = TeamPermission.objects.get(project=project, target=team)
        except ObjectDoesNotExist:
            return ErrorResponse(
                {"error": (f"A permission for this team: `{team}` does not exist.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not permission.is_active:
            return ErrorResponse(
                {
                    "error": (
                        f"The permission for this team: `{team}` "
                        "is inactive. Recreate the permission."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        permission.level = access_level
        permission.save()

        # Refresh the `modified_date` field
        project.save()

        permission_serializer = TeamPermissionSerializer(permission)
        project_serializer = ProjectSerializer(project, context={"user": request.user})

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, *args, **kwargs):
        serializer = TeamRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = serializer.validated_data["team"]
        project = self.get_object()
        try:
            permission = TeamPermission.objects.get(project=project, target=team)

        except ObjectDoesNotExist:
            return ErrorResponse(
                {"error": (f"A permission for this team: `{team}` does not exist.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Deactivate the project permission
        permission.deactivate(deactivated_by=request.user)
        permission.save()

        # Refresh the `modified_date` field
        project.save()

        project_serializer = ProjectSerializer(project, context={"user": request.user})

        return SuccessResponse(
            {
                "project": project_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )
