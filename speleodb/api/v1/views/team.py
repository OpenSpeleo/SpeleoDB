#!/usr/bin/env python
# -*- coding: utf-8 -*-

from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import UserHasLeaderAccess
from speleodb.api.v1.permissions import UserHasLeaderAccessOrReadOnlyForMembers
from speleodb.api.v1.permissions import UserHasMemberAccess
from speleodb.api.v1.serializers import SurveyTeamListSerializer
from speleodb.api.v1.serializers import SurveyTeamSerializer
from speleodb.users.models import SurveyTeam
from speleodb.utils.api_decorators import method_permission_classes
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse


class CreateTeamApiView(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SurveyTeamSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"user": request.user}
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class TeamApiView(GenericAPIView):
    queryset = SurveyTeam.objects.all()
    permission_classes = [
        permissions.IsAuthenticated,
        UserHasLeaderAccessOrReadOnlyForMembers,
    ]
    serializer_class = SurveyTeamSerializer
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        team = self.get_object()
        serializer = self.get_serializer(team, context={"user": request.user})

        return SuccessResponse(serializer.data)

    def put(self, request, *args, **kwargs):
        team = self.get_object()
        serializer = self.get_serializer(
            team, data=request.data, context={"user": request.user}
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_200_OK)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def patch(self, request, *args, **kwargs):
        team = self.get_object()
        serializer = self.get_serializer(
            team, data=request.data, context={"user": request.user}, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_200_OK)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, *args, **kwargs):
        team = self.get_object()
        team_id = team.id
        team.delete()

        return SuccessResponse({"id": str(team_id)})


class ListUserTeams(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SurveyTeamListSerializer
    lookup_field = "id"

    @method_permission_classes((UserHasMemberAccess,))
    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            request.user.teams, context={"user": request.user}
        )

        return SuccessResponse(serializer.data)
