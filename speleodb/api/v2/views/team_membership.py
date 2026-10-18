# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.schema_errors import API_ERROR
from speleodb.api.schema_helpers import response_object
from speleodb.api.v2.permissions import IsReadOnly
from speleodb.api.v2.permissions import UserHasLeaderAccess
from speleodb.api.v2.permissions import UserHasMemberAccess
from speleodb.api.v2.serializers import SurveyTeamMembershipSerializer
from speleodb.api.v2.serializers import SurveyTeamSerializer
from speleodb.api.v2.serializers import UserRequestSerializer
from speleodb.api.v2.serializers import UserRequestWithTeamRoleSerializer
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.users.models import User
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response


class TeamMembershipApiView(GenericAPIView[SurveyTeam], SDBAPIViewMixin):
    queryset = SurveyTeam.objects.all()
    permission_classes = [UserHasLeaderAccess | (IsReadOnly & UserHasMemberAccess)]
    serializer_class = SurveyTeamSerializer
    lookup_field = "id"

    @extend_schema(
        responses={
            200: response_object(
                "TeamMembershipApiViewGetResponse",
                team=SurveyTeamSerializer(),
                membership=SurveyTeamMembershipSerializer(),
            ),
            403: API_ERROR,
            404: API_ERROR,
        }
    )
    @extend_schema(operation_id="v2_teams_memberships_detail_retrieve")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        team = self.get_object()
        user = self.get_user()
        try:
            membership = SurveyTeamMembership.objects.get(
                team=team, user=user, is_active=True
            )
        except ObjectDoesNotExist:
            return ErrorResponse(
                {"error": (f"A membership for this user: `{user}` does not exist.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        membership_serializer = SurveyTeamMembershipSerializer(membership)
        team_serializer = SurveyTeamSerializer(team, context={"user": user})

        return SuccessResponse(
            {
                "team": team_serializer.data,
                "membership": membership_serializer.data,
            }
        )

    @extend_schema(request=UserRequestWithTeamRoleSerializer)
    @extend_schema(
        responses={
            201: response_object(
                "TeamMembershipApiViewPostResponse",
                team=SurveyTeamSerializer(),
                membership=SurveyTeamMembershipSerializer(),
            ),
            400: API_ERROR,
            403: API_ERROR,
        }
    )
    @extend_schema(operation_id="v2_teams_memberships_detail_create")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        serializer = UserRequestWithTeamRoleSerializer(
            data=request.data, context={"requesting_user": user}
        )

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team: SurveyTeam = self.get_object()
        target_user: User = serializer.validated_data["user"]
        membership, created = SurveyTeamMembership.objects.get_or_create(
            team=team,
            user=target_user,
        )

        if not created:
            if membership.is_active:
                return ErrorResponse(
                    {
                        "error": (
                            f"Membership for this user: `{target_user}` already exists."
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
        team_serializer = SurveyTeamSerializer(team, context={"user": user})

        return SuccessResponse(
            {
                "team": team_serializer.data,
                "membership": membership_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=UserRequestWithTeamRoleSerializer)
    @extend_schema(
        responses={
            200: response_object(
                "TeamMembershipApiViewPutResponse",
                team=SurveyTeamSerializer(),
                membership=SurveyTeamMembershipSerializer(),
            ),
            400: API_ERROR,
            403: API_ERROR,
            404: API_ERROR,
        }
    )
    @extend_schema(operation_id="v2_teams_memberships_detail_update")
    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        serializer = UserRequestWithTeamRoleSerializer(
            data=request.data, context={"requesting_user": user}
        )

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team: SurveyTeam = self.get_object()
        try:
            target_user: User = serializer.validated_data["user"]
            membership = SurveyTeamMembership.objects.get(
                team=team,
                user=target_user,
            )
        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        "A membership for this user: "
                        f"`{serializer.validated_data['user']}` does not exist."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
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
        team_serializer = SurveyTeamSerializer(team, context={"user": user})

        return SuccessResponse(
            {
                "team": team_serializer.data,
                "membership": membership_serializer.data,
            }
        )

    @extend_schema(request=UserRequestSerializer)
    @extend_schema(
        responses={
            200: response_object(
                "TeamMembershipApiViewDeleteResponse", team=SurveyTeamSerializer()
            ),
            400: API_ERROR,
            403: API_ERROR,
            404: API_ERROR,
        }
    )
    @extend_schema(operation_id="v2_teams_memberships_detail_destroy")
    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        serializer = UserRequestSerializer(
            data=request.data, context={"requesting_user": user}
        )

        if not serializer.is_valid():
            return ErrorResponse(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team: SurveyTeam = self.get_object()
        try:
            target_user: User = serializer.validated_data["user"]
            membership = SurveyTeamMembership.objects.get(
                team=team, user=target_user, is_active=True
            )
        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        "A membership for this user: "
                        f"`{serializer.validated_data['user']}` does not exist."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Deactivate the user membership to the team
        membership.deactivate(deactivated_by=user)
        membership.save()

        # Refresh the `modified_date` field
        team.save()

        team_serializer = SurveyTeamSerializer(team, context={"user": user})

        return SuccessResponse(
            {"team": team_serializer.data},
            status=status.HTTP_200_OK,
        )


class TeamMembershipListApiView(GenericAPIView[SurveyTeam], SDBAPIViewMixin):
    queryset = SurveyTeam.objects.all()
    permission_classes = [UserHasMemberAccess]
    serializer_class = SurveyTeamSerializer
    lookup_field = "id"

    @extend_schema(
        responses={
            200: response_object(
                "TeamMembershipListApiViewGetResponse",
                team=SurveyTeamSerializer(),
                memberships=SurveyTeamMembershipSerializer(many=True),
            ),
            403: API_ERROR,
        }
    )
    @extend_schema(operation_id="v2_teams_memberships_retrieve")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        team: SurveyTeam = self.get_object()
        user = self.get_user()
        team_mbrshps = SurveyTeamMembership.objects.filter(team=team, is_active=True)

        membership_serializer = SurveyTeamMembershipSerializer(team_mbrshps, many=True)
        team_serializer = SurveyTeamSerializer(team, context={"user": user})

        return SuccessResponse(
            {
                "team": team_serializer.data,
                "memberships": membership_serializer.data,
            }
        )
