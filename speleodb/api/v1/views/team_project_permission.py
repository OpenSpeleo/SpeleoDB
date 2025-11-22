# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import IsReadOnly
from speleodb.api.v1.permissions import ProjectUserHasAdminAccess
from speleodb.api.v1.permissions import ProjectUserHasReadAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.serializers import ProjectTeamPermissionListSerializer
from speleodb.api.v1.serializers import ProjectTeamPermissionSerializer
from speleodb.api.v1.serializers import SurveyTeamSerializer
from speleodb.api.v1.serializers import TeamRequestSerializer
from speleodb.api.v1.serializers import TeamRequestWithProjectLevelSerializer
from speleodb.surveys.models import Project
from speleodb.surveys.models import TeamProjectPermission
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response

    from speleodb.users.models import SurveyTeam


class ProjectTeamPermissionListApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [ProjectUserHasReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        project = self.get_object()
        user = self.get_user()
        team_permissions = project.team_permissions

        project_serializer = ProjectSerializer(project, context={"user": user})
        permission_serializer = ProjectTeamPermissionListSerializer(team_permissions)  # type: ignore[arg-type]

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permissions": permission_serializer.data,
            }
        )


class ProjectTeamPermissionSpecificApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [
        ProjectUserHasAdminAccess | (IsReadOnly & ProjectUserHasReadAccess)
    ]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        project = self.get_object()
        user = self.get_user()

        serializer = TeamRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = serializer.validated_data["team"]

        try:
            permission = TeamProjectPermission.objects.get(
                project=project,
                target=team,
                is_active=True,
            )

        except ObjectDoesNotExist:
            return ErrorResponse(
                {"error": (f"A permission for this team: `{team}` does not exist.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        permission_serializer = ProjectTeamPermissionSerializer(permission)
        project_serializer = ProjectSerializer(project, context={"user": user})
        team_serializer = SurveyTeamSerializer(team, context={"user": user})

        return SuccessResponse(
            {
                "permission": permission_serializer.data,
                "project": project_serializer.data,
                "team": team_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        serializer = TeamRequestWithProjectLevelSerializer(
            data=request.data, context={"requesting_user": user}
        )

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        perm_data = serializer.validated_data

        project = self.get_object()
        target_team: SurveyTeam = perm_data["team"]
        permission, created = TeamProjectPermission.objects.get_or_create(
            project=project,
            target=target_team,
        )

        if not created:
            if permission.is_active:
                return ErrorResponse(
                    {
                        "error": (
                            f"The permission for this team: `{perm_data['team']}` "
                            "already exists."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Reactivate permission
            permission.reactivate(level=perm_data["level"])

        else:
            # Now assign the role. Couldn't do it during object creation because
            # of the use of `get_or_create`
            permission.level = perm_data["level"]

        permission.save()

        # Refresh the `modified_date` field
        project.save()

        # Recurively void permission cache for all team members
        for membership in target_team.get_all_memberships():
            membership.user.void_permission_cache()

        permission_serializer = ProjectTeamPermissionSerializer(permission)
        project_serializer = ProjectSerializer(project, context={"user": user})

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        serializer = TeamRequestWithProjectLevelSerializer(
            data=request.data, context={"requesting_user": user}
        )

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_team: SurveyTeam = serializer.validated_data["team"]
        access_level = serializer.validated_data["level"]

        project = self.get_object()
        try:
            permission = TeamProjectPermission.objects.get(
                project=project,
                target=target_team,
                is_active=True,
            )

        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this team: `{target_team}` does not exist."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        permission.level = access_level
        permission.save()

        # Refresh the `modified_date` field
        project.save()

        # Recurively void permission cache for all team members
        for membership in target_team.get_all_memberships():
            membership.user.void_permission_cache()

        permission_serializer = ProjectTeamPermissionSerializer(permission)
        project_serializer = ProjectSerializer(project, context={"user": user})

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        serializer = TeamRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_team: SurveyTeam = serializer.validated_data["team"]
        project = self.get_object()
        try:
            permission = TeamProjectPermission.objects.get(
                project=project,
                target=target_team,
                is_active=True,
            )

        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this team: `{target_team}` does not exist."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Deactivate the project permission
        permission.deactivate(deactivated_by=user)
        permission.save()

        # Refresh the `modified_date` field
        project.save()

        # Recurively void permission cache for all team members
        for membership in target_team.get_all_memberships():
            membership.user.void_permission_cache()

        project_serializer = ProjectSerializer(project, context={"user": user})

        return SuccessResponse(
            {
                "project": project_serializer.data,
            },
            status=status.HTTP_200_OK,
        )
