from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from speleodb.surveys.models import TeamPermission
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.users.models import User


class UserRequestSerializer(serializers.Serializer):
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
        choices=[name for _, name in SurveyTeamMembership.Role.choices]
    )

    def validate_role(self, value: str) -> SurveyTeamMembership.Role:
        return getattr(SurveyTeamMembership.Role, value.upper())


class TeamRequestSerializer(serializers.Serializer):
    team = serializers.IntegerField()

    def validate_team(self, value: int) -> SurveyTeam:
        try:
            team = SurveyTeam.objects.get(id=value)

        except ObjectDoesNotExist as e:
            raise serializers.ValidationError(
                f"The team `{team}` does not exist."
            ) from e

        return team


class TeamRequestWithProjectLevelSerializer(TeamRequestSerializer):
    level = serializers.ChoiceField(
        choices=[name for _, name in TeamPermission.Level.choices]
    )

    def validate_level(self, value: str) -> TeamPermission.Level:
        return getattr(TeamPermission.Level, value.upper())
