# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v2.permissions import IsObjectCreation
from speleodb.api.v2.permissions import IsReadOnly
from speleodb.api.v2.permissions import UserHasLeaderAccess
from speleodb.api.v2.permissions import UserHasMemberAccess
from speleodb.api.v2.serializers import SurveyTeamSerializer
from speleodb.users.models import SurveyTeam
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response


class TeamApiView(GenericAPIView[SurveyTeam], SDBAPIViewMixin):
    queryset = SurveyTeam.objects.all()
    serializer_class = SurveyTeamSerializer

    permission_classes = [
        (permissions.IsAuthenticated & IsObjectCreation)
        | (IsReadOnly & UserHasMemberAccess)
    ]

    @extend_schema(operation_id="v2_teams_list")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        serializer = self.get_serializer(
            user.teams,
            context={"user": user},
            many=True,
        )

        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        serializer = self.get_serializer(
            data=request.data,
            context={"user": user},
        )
        if serializer.is_valid():
            serializer.save()

            return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class TeamSpecificApiView(GenericAPIView[SurveyTeam], SDBAPIViewMixin):
    queryset = SurveyTeam.objects.all()
    permission_classes = [UserHasLeaderAccess | (IsReadOnly & UserHasMemberAccess)]
    serializer_class = SurveyTeamSerializer
    lookup_field = "id"

    @extend_schema(operation_id="v2_team_retrieve")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        team = self.get_object()
        user = self.get_user()
        serializer = self.get_serializer(team, context={"user": user})

        return SuccessResponse(serializer.data)

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        team: SurveyTeam = self.get_object()
        user = self.get_user()
        serializer = self.get_serializer(
            team,
            data=request.data,
            context={"user": user},
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        team = self.get_object()
        user = self.get_user()
        serializer = self.get_serializer(
            team,
            data=request.data,
            context={"user": user},
            partial=True,
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # Soft-delete: we do not hard-delete the team. Mirroring
        # `ProjectSpecificApiView.delete` (`speleodb/api/v2/views/project.py`):
        # deactivate all memberships and team project permissions.
        #
        # This renders the team invisible to every user without touching any
        # historical data — `User.teams` filters by
        # `memberships__is_active=True`, `UserHasMemberAccess` rejects anyone
        # without an active membership, and team project permissions only
        # grant project access while active (see `Project.team_permissions`).
        user = self.get_user()
        team = self.get_object()
        team_id = team.id

        for membership in team.memberships.filter(is_active=True):
            membership.deactivate(deactivated_by=user)

        for team_perm in team.project_permissions.filter(is_active=True):
            team_perm.deactivate(deactivated_by=user)

        return SuccessResponse({"id": str(team_id)}, status=status.HTTP_200_OK)
