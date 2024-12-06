#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from speleodb.api.v1.permissions import UserHasLeaderAccess
from speleodb.api.v1.permissions import UserHasMemberAccess
from speleodb.users.api.v1.serializers import SurveyTeamMembershipSerializer
from speleodb.users.api.v1.serializers import SurveyTeamSerializer
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.users.models import User
from speleodb.utils.api_decorators import method_permission_classes
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

logger = logging.getLogger(__name__)


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
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SurveyTeamSerializer
    lookup_field = "id"

    @method_permission_classes((UserHasMemberAccess,))
    def get(self, request, *args, **kwargs):
        team = self.get_object()
        serializer = self.get_serializer(team, context={"user": request.user})

        return SuccessResponse({"team": serializer.data})

    @method_permission_classes((UserHasLeaderAccess,))
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

    @method_permission_classes((UserHasLeaderAccess,))
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

    @method_permission_classes((UserHasLeaderAccess,))
    def delete(self, request, *args, **kwargs):
        team = self.get_object()
        team_id = team.id
        team.delete()

        return SuccessResponse({"id": str(team_id)})


class TeamMembershipApiView(GenericAPIView):
    queryset = SurveyTeam.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasLeaderAccess]
    serializer_class = SurveyTeamSerializer
    lookup_field = "id"

    def _process_request_data(self, data, skip_role=False):
        membership_data = {}
        for key in ["user", "role"]:
            try:
                if key == "role" and skip_role:
                    continue

                value = data[key]

                if key == "role":
                    if not isinstance(value, str) or value.upper() not in [
                        name for _, name in SurveyTeamMembership.Role.choices
                    ]:
                        return ErrorResponse(
                            {"error": f"Invalid value received for `{key}`: `{value}`"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    membership_data[key] = getattr(
                        SurveyTeamMembership.Role, value.upper()
                    )

                elif key in "user":
                    try:
                        membership_data[key] = User.objects.get(email=value)
                    except ObjectDoesNotExist:
                        return ErrorResponse(
                            {"error": f"The user: `{value}` does not exist."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if not membership_data[key].is_active:
                        return ErrorResponse(
                            {"error": f"The user: `{value}` is inactive."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            except KeyError:
                return ErrorResponse(
                    {"error": f"Attribute: `{key}` is missing"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return membership_data

    def post(self, request, *args, **kwargs):
        team = self.get_object()

        membership_data = self._process_request_data(data=request.data)

        # An Error occured
        if isinstance(membership_data, Response):
            return membership_data

        # Can't edit your own membership
        if request.user == membership_data["user"]:
            # This by default make no sense because you need to be team leader
            # to create membership. So you obviously can't create membership for
            # yourself. Added just as safety and logical consistency.
            return ErrorResponse(
                {"error": ("A user can not edit their own membership")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership, created = SurveyTeamMembership.objects.get_or_create(
            team=team, user=membership_data["user"]
        )

        if not created and membership.is_active:
            return ErrorResponse(
                {
                    "error": (
                        f"A membership for this user: `{membership_data['user']}` "
                        "already exist."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.reactivate(role=membership_data["role"])

        membership_serializer = SurveyTeamMembershipSerializer(membership)
        team_serializer = SurveyTeamSerializer(team, context={"user": request.user})

        # Refresh the `modified_date` field
        team.save()

        return SuccessResponse(
            {
                "team": team_serializer.data,
                "membership": membership_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, *args, **kwargs):
        team = self.get_object()

        membership_data = self._process_request_data(data=request.data)

        # An Error occured
        if isinstance(membership_data, Response):
            return membership_data

        # Can't edit your own membership
        if request.user == membership_data["user"]:
            return ErrorResponse(
                {"error": ("A user can not edit their own membership")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            membership = SurveyTeamMembership.objects.get(
                team=team, user=membership_data["user"]
            )
        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A membership for this user: `{membership_data['user']}` "
                        "does not exist."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not membership.is_active:
            return ErrorResponse(
                {
                    "error": (
                        f"The membership for this user: `{membership_data['user']}` "
                        "is inactive. Recreate the membership."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.role = membership_data["role"]
        membership.save()

        membership_serializer = SurveyTeamMembershipSerializer(membership)
        team_serializer = SurveyTeamSerializer(team, context={"user": request.user})

        # Refresh the `modified_date` field
        team.save()

        return SuccessResponse(
            {
                "team": team_serializer.data,
                "membership": membership_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, *args, **kwargs):
        team = self.get_object()

        membership_data = self._process_request_data(data=request.data, skip_role=True)

        # An Error occured
        if isinstance(membership_data, Response):
            return membership_data

        # Can't edit your own membership
        if request.user == membership_data["user"]:
            return ErrorResponse(
                {"error": ("A user can not edit their own membership")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            membership = SurveyTeamMembership.objects.get(
                team=team, user=membership_data["user"]
            )
        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A membership for this user: `{membership_data['user']}` "
                        "does not exist."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.deactivate(deactivated_by=request.user)
        team_serializer = SurveyTeamSerializer(team, context={"user": request.user})

        # Refresh the `modified_date` field
        team.save()

        return SuccessResponse(
            {
                "team": team_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )
