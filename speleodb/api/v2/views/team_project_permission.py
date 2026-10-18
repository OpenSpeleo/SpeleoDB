# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.schema_errors import API_ERROR
from speleodb.api.schema_helpers import response_object
from speleodb.api.v2.permissions import IsReadOnly
from speleodb.api.v2.permissions import SDB_AdminAccess
from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.serializers import ProjectSerializer
from speleodb.api.v2.serializers import ProjectTeamPermissionSerializer
from speleodb.api.v2.serializers import SurveyTeamSerializer
from speleodb.api.v2.serializers import TeamRequestSerializer
from speleodb.api.v2.serializers import TeamRequestWithProjectLevelSerializer
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
    permission_classes = [SDB_ReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    @extend_schema(
        responses={
            200: response_object(
                "ProjectTeamPermissionListApiViewGetResponse",
                project=ProjectSerializer(),
                permissions=ProjectTeamPermissionSerializer(many=True),
            ),
            403: API_ERROR,
        }
    )
    @extend_schema(operation_id="v2_projects_permissions_team_retrieve")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        project = self.get_object()
        user = self.get_user()
        team_permissions = project.team_permissions

        project_serializer = ProjectSerializer(project, context={"user": user})
        permission_serializer = ProjectTeamPermissionSerializer(
            team_permissions, many=True
        )

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permissions": permission_serializer.data,
            }
        )


class ProjectTeamPermissionSpecificApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [SDB_AdminAccess | (IsReadOnly & SDB_ReadAccess)]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    @extend_schema(
        parameters=[OpenApiParameter("team", OpenApiTypes.UUID, required=True)]
    )
    @extend_schema(
        responses={
            200: response_object(
                "ProjectTeamPermissionSpecificApiViewGetResponse",
                permission=ProjectTeamPermissionSerializer(),
                project=ProjectSerializer(),
                team=SurveyTeamSerializer(),
            ),
            400: API_ERROR,
            403: API_ERROR,
            404: API_ERROR,
        }
    )
    @extend_schema(operation_id="v2_projects_permission_team_detail_retrieve")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        project = self.get_object()
        user = self.get_user()

        # Browser fetch cannot send a GET body.
        serializer = TeamRequestSerializer(data=request.query_params)

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

    @extend_schema(request=TeamRequestWithProjectLevelSerializer)
    @extend_schema(
        responses={
            201: response_object(
                "ProjectTeamPermissionSpecificApiViewPostResponse",
                project=ProjectSerializer(),
                permission=ProjectTeamPermissionSerializer(),
            ),
            400: API_ERROR,
            403: API_ERROR,
        }
    )
    @extend_schema(operation_id="v2_projects_permission_team_detail_create")
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

            # `reactivate` persists internally; no extra `save()` needed here.
            permission.reactivate(level=perm_data["level"])

        else:
            # Fresh row from `get_or_create` — assign the level and persist.
            permission.level = perm_data["level"]
            permission.save()

        # Refresh the `modified_date` field (single-column UPDATE).
        project.save(update_fields=["modified_date"])

        permission_serializer = ProjectTeamPermissionSerializer(permission)
        project_serializer = ProjectSerializer(project, context={"user": user})

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=TeamRequestWithProjectLevelSerializer)
    @extend_schema(
        responses={
            200: response_object(
                "ProjectTeamPermissionSpecificApiViewPutResponse",
                project=ProjectSerializer(),
                permission=ProjectTeamPermissionSerializer(),
            ),
            400: API_ERROR,
            403: API_ERROR,
            404: API_ERROR,
        }
    )
    @extend_schema(operation_id="v2_projects_permission_team_detail_update")
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
        permission.save(update_fields=["level", "modified_date"])

        # Refresh the `modified_date` field (single-column UPDATE).
        project.save(update_fields=["modified_date"])

        permission_serializer = ProjectTeamPermissionSerializer(permission)
        project_serializer = ProjectSerializer(project, context={"user": user})

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(request=TeamRequestSerializer)
    @extend_schema(
        responses={
            200: response_object(
                "ProjectTeamPermissionSpecificApiViewDeleteResponse",
                project=ProjectSerializer(),
            ),
            400: API_ERROR,
            403: API_ERROR,
            404: API_ERROR,
        }
    )
    @extend_schema(operation_id="v2_projects_permission_team_detail_destroy")
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

        # `deactivate` persists internally; no explicit save() needed.
        permission.deactivate(deactivated_by=user)

        # Refresh the `modified_date` field (single-column UPDATE).
        project.save(update_fields=["modified_date"])

        project_serializer = ProjectSerializer(project, context={"user": user})

        return SuccessResponse(
            {
                "project": project_serializer.data,
            },
            status=status.HTTP_200_OK,
        )
