#!/usr/bin/env python
# -*- coding: utf-8 -*-

from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import IsObjectCreation
from speleodb.api.v1.permissions import IsReadOnly
from speleodb.api.v1.permissions import UserHasLeaderAccess
from speleodb.api.v1.permissions import UserHasMemberAccess
from speleodb.api.v1.serializers import SurveyTeamSerializer
from speleodb.users.models import SurveyTeam
from speleodb.users.models import User
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse


class TeamApiView(GenericAPIView):
    serializer_class = SurveyTeamSerializer
    queryset = SurveyTeam.objects.all()

    permission_classes = [
        (permissions.IsAuthenticated & IsObjectCreation)
        | (IsReadOnly & UserHasMemberAccess)
    ]

    def get(self, request, *args, **kwargs):
        user: User = request.user
        serializer = self.get_serializer(
            user.teams, context={"user": request.user}, many=True
        )

        return SuccessResponse(serializer.data)

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


class TeamSpecificApiView(GenericAPIView):
    queryset = SurveyTeam.objects.all()
    permission_classes = [UserHasLeaderAccess | (IsReadOnly & UserHasMemberAccess)]
    serializer_class = SurveyTeamSerializer
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        team: SurveyTeam = self.get_object()
        serializer = self.get_serializer(team, context={"user": request.user})

        return SuccessResponse(serializer.data)

    def put(self, request, *args, **kwargs):
        team: SurveyTeam = self.get_object()
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
        team: SurveyTeam = self.get_object()
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
        team: SurveyTeam = self.get_object()
        team_id = team.id
        team.delete()

        return SuccessResponse({"id": str(team_id)}, status=status.HTTP_204_NO_CONTENT)
