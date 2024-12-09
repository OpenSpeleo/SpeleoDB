#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import IsReadOnly
from speleodb.api.v1.permissions import UserHasLeaderAccess
from speleodb.api.v1.permissions import UserHasMemberAccess
from speleodb.api.v1.serializers import SurveyTeamMembershipListSerializer
from speleodb.api.v1.serializers import SurveyTeamMembershipSerializer
from speleodb.api.v1.serializers import SurveyTeamSerializer
from speleodb.api.v1.serializers import UserRequestSerializer
from speleodb.api.v1.serializers import UserRequestWithTeamRoleSerializer
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse


class TeamMembershipApiView(GenericAPIView):
    queryset = SurveyTeam.objects.all()
    permission_classes = [UserHasLeaderAccess | (IsReadOnly & UserHasMemberAccess)]
    serializer_class = SurveyTeamSerializer
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        team = self.get_object()
        try:
            membership = SurveyTeamMembership.objects.get(
                team=team, user=request.user, is_active=True
            )
        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        "A membership for this user: "
                        f"`{request.user}` does not exist."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership_serializer = SurveyTeamMembershipSerializer(membership)
        team_serializer = SurveyTeamSerializer(team, context={"user": request.user})

        return SuccessResponse(
            {
                "team": team_serializer.data,
                "membership": membership_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        serializer = UserRequestWithTeamRoleSerializer(
            data=request.data, context={"requesting_user": request.user}
        )

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = self.get_object()
        membership, created = SurveyTeamMembership.objects.get_or_create(
            team=team, user=serializer.validated_data["user"]
        )

        if not created:
            if membership.is_active:
                return ErrorResponse(
                    {
                        "error": (
                            "A membership for this user: "
                            f"`{serializer.validated_data['user']}` already exist."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Reactivate membership
            membership.reactivate(role=serializer.validated_data["role"])
            membership.save()
        else:
            # Now assign the role. Couldn't do it during object creation because
            # of the use of `get_or_create`
            membership.role = serializer.validated_data["role"]
            membership.save()

        # Refresh the `modified_date` field
        team.save()

        membership_serializer = SurveyTeamMembershipSerializer(membership)
        team_serializer = SurveyTeamSerializer(team, context={"user": request.user})

        return SuccessResponse(
            {
                "team": team_serializer.data,
                "membership": membership_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, *args, **kwargs):
        serializer = UserRequestWithTeamRoleSerializer(
            data=request.data, context={"requesting_user": request.user}
        )

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = self.get_object()
        try:
            membership = SurveyTeamMembership.objects.get(
                team=team,
                user=serializer.validated_data["user"],
            )
        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        "A membership for this user: "
                        f"`{serializer.validated_data['user']}` does not exist."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not membership.is_active:
            return ErrorResponse(
                {
                    "error": (
                        "The membership for this user: "
                        f"`{serializer.validated_data['user']}` "
                        "is inactive. Recreate the membership."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Change the role of the user
        membership.role = serializer.validated_data["role"]
        membership.save()

        # Refresh the `modified_date` field
        team.save()

        membership_serializer = SurveyTeamMembershipSerializer(membership)
        team_serializer = SurveyTeamSerializer(team, context={"user": request.user})

        return SuccessResponse(
            {
                "team": team_serializer.data,
                "membership": membership_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):
        serializer = UserRequestSerializer(
            data=request.data, context={"requesting_user": request.user}
        )

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = self.get_object()
        try:
            membership = SurveyTeamMembership.objects.get(
                team=team, user=serializer.validated_data["user"], is_active=True
            )
        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        "A membership for this user: "
                        f"`{serializer.validated_data['user']}` does not exist."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Deactivate the user membership to the team
        membership.deactivate(deactivated_by=request.user)
        membership.save()

        # Refresh the `modified_date` field
        team.save()

        team_serializer = SurveyTeamSerializer(team, context={"user": request.user})

        return SuccessResponse(
            {
                "team": team_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class TeamMembershipListApiView(GenericAPIView):
    queryset = SurveyTeam.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasLeaderAccess]
    serializer_class = SurveyTeamSerializer
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        team = self.get_object()
        membership_list = SurveyTeamMembership.objects.filter(team=team, is_active=True)

        membership_serializer = SurveyTeamMembershipListSerializer(membership_list)
        team_serializer = SurveyTeamSerializer(team, context={"user": request.user})

        return SuccessResponse(
            {
                "team": team_serializer.data,
                "memberships": membership_serializer.data,
            },
            status=status.HTTP_200_OK,
        )
