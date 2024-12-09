#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.exceptions import ObjectDoesNotExist
from django_countries import countries
from rest_framework import serializers

from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.utils.serializer_fields import CustomChoiceField


class SurveyTeamSerializer(serializers.ModelSerializer):
    country = CustomChoiceField(choices=countries)

    class Meta:
        fields = "__all__"
        model = SurveyTeam

    def create(self, validated_data):
        team = super().create(validated_data)

        # assign current user as project admin
        SurveyTeamMembership.objects.create(
            team=team,
            user=self.context.get("user"),
            role=SurveyTeamMembership.Role.LEADER,
        )

        return team

    def get_permission(self, obj):
        if isinstance(obj, dict):
            # Unsaved object
            return None

        user = self.context.get("user")

        try:
            membership = obj.get_membership(user=user)
            if membership is None:
                return None
        except ObjectDoesNotExist:
            return None

        return membership.role


class SurveyTeamMembershipSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    role = CustomChoiceField(choices=SurveyTeamMembership.Role, source="_role")

    class Meta:
        fields = ("user", "role", "creation_date", "modified_date")
        model = SurveyTeamMembership