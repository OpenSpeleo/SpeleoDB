# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from speleodb.common.enums import PermissionLevel
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembershipRole
from speleodb.users.models import User

if TYPE_CHECKING:
    import uuid


class UserRequestSerializer(serializers.Serializer[User]):
    user = serializers.EmailField()

    def validate_user(self, value: str) -> User:
        try:
            user = User.objects.get(email=value)

        except ObjectDoesNotExist as e:
            raise serializers.ValidationError(
                f"The user `{value}` does not exist."
            ) from e

        if not user.is_active:
            raise serializers.ValidationError(f"The user `{value}` is inactive.")

        # A user can't edit their own membership
        # This by default make no sense because you need to be team leader
        # to create membership. So you obviously can't create membership for
        # yourself. Added just as safety and logical consistency.
        if self.context.get("requesting_user") == user:
            raise serializers.ValidationError(
                "A user can not edit their own membership"
            )

        return user


class UserRequestWithTeamRoleSerializer(UserRequestSerializer):
    role = serializers.ChoiceField(
        choices=[name for _, name in SurveyTeamMembershipRole.choices]
    )

    def validate_role(self, value: str) -> SurveyTeamMembershipRole:
        return SurveyTeamMembershipRole.from_str(value.upper())


class TeamRequestSerializer(serializers.Serializer[SurveyTeam]):
    team = serializers.UUIDField()

    def validate_team(self, value: uuid.UUID) -> SurveyTeam:
        try:
            team = SurveyTeam.objects.get(id=value)

        except ObjectDoesNotExist as e:
            raise serializers.ValidationError(
                f"The team `{value}` does not exist."
            ) from e

        return team


class TeamRequestWithProjectLevelSerializer(TeamRequestSerializer):
    level = serializers.ChoiceField(
        choices=[name for _, name in PermissionLevel.choices]
    )

    def validate_level(self, value: str) -> PermissionLevel:
        return PermissionLevel.from_str(value.upper())
