# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

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
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response


class ProjectTeamPermissionListView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        project = self.get_object()
        user = self.get_user()
        team_permissions = project.team_permissions

        project_serializer = ProjectSerializer(project, context={"user": user})
        permission_serializer = TeamPermissionListSerializer(team_permissions)  # type: ignore[arg-type]

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permissions": permission_serializer.data,
            }
        )


class ProjectTeamPermissionView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [UserHasAdminAccess | (IsReadOnly & UserHasReadAccess)]
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
            permission = TeamPermission.objects.get(
                project=project,
                target=team,
                is_active=True,
            )

        except ObjectDoesNotExist:
            return ErrorResponse(
                {"error": (f"A permission for this team: `{team}` does not exist.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        permission_serializer = TeamPermissionSerializer(permission)
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
        permission, created = TeamPermission.objects.get_or_create(
            project=project, target=perm_data["team"]
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

        permission_serializer = TeamPermissionSerializer(permission)
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

        team = serializer.validated_data["team"]
        access_level = serializer.validated_data["level"]

        project = self.get_object()
        try:
            permission = TeamPermission.objects.get(
                project=project,
                target=team,
                is_active=True,
            )

        except ObjectDoesNotExist:
            return ErrorResponse(
                {"error": (f"A permission for this team: `{team}` does not exist.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        permission.level = access_level
        permission.save()

        # Refresh the `modified_date` field
        project.save()

        permission_serializer = TeamPermissionSerializer(permission)
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

        team = serializer.validated_data["team"]
        project = self.get_object()
        try:
            permission = TeamPermission.objects.get(
                project=project,
                target=team,
                is_active=True,
            )

        except ObjectDoesNotExist:
            return ErrorResponse(
                {"error": (f"A permission for this team: `{team}` does not exist.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Deactivate the project permission
        permission.deactivate(deactivated_by=user)
        permission.save()

        # Refresh the `modified_date` field
        project.save()

        project_serializer = ProjectSerializer(project, context={"user": user})

        return SuccessResponse(
            {
                "project": project_serializer.data,
            },
            status=status.HTTP_204_NO_CONTENT,
        )
