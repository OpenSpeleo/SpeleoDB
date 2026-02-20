# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any
from typing import ClassVar

from django.core.exceptions import ObjectDoesNotExist
from django_countries import countries
from rest_framework import serializers

from speleodb.common.enums import SurveyTeamMembershipRole
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.utils.serializer_fields import CustomChoiceField
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin


class SurveyTeamSerializer(
    SanitizedFieldsMixin, serializers.ModelSerializer[SurveyTeam]
):
    sanitized_fields: ClassVar[list[str]] = ["name", "description"]

    country = CustomChoiceField(choices=list(countries))
    role = serializers.SerializerMethodField()

    class Meta:
        fields = "__all__"
        model = SurveyTeam

    def create(self, validated_data: Any) -> Any:
        team = super().create(validated_data)

        if (user := self.context.get("user")) is None:
            raise ValueError

        # assign current user as project admin
        SurveyTeamMembership.objects.create(
            team=team,
            user=user,
            role=SurveyTeamMembershipRole.LEADER,
        )

        return team

    def get_role(self, obj: SurveyTeam) -> None | SurveyTeamMembershipRole:
        if isinstance(obj, dict):
            # Unsaved object
            return None

        user = self.context.get("user")

        if user is None:
            return None

        try:
            return SurveyTeamMembershipRole(obj.get_membership(user=user).role)
        except ObjectDoesNotExist:
            return None


class SurveyTeamMembershipSerializer(serializers.ModelSerializer[SurveyTeamMembership]):
    user = serializers.StringRelatedField()  # type: ignore[var-annotated]
    role = CustomChoiceField(choices=SurveyTeamMembershipRole)  # type: ignore[arg-type]

    class Meta:
        fields = ("user", "team", "role", "creation_date", "modified_date")
        model = SurveyTeamMembership
