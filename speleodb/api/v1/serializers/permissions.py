#!/usr/bin/env python
# -*- coding: utf-8 -*-

from rest_framework import serializers

from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.utils.serializer_fields import CustomChoiceField


class UserPermissionSerializer(serializers.ModelSerializer[UserPermission]):
    user = serializers.PrimaryKeyRelatedField(read_only=True, source="target")  # type: ignore[var-annotated]
    level = CustomChoiceField(choices=[x for x, _ in PermissionLevel.choices])

    class Meta:
        fields = ("user", "level", "creation_date", "modified_date")
        model = UserPermission


class TeamPermissionSerializer(serializers.ModelSerializer[TeamPermission]):
    team = serializers.PrimaryKeyRelatedField(read_only=True, source="target")  # type: ignore[var-annotated]
    level = CustomChoiceField(choices=[x for x, _ in PermissionLevel.choices_no_admin])

    class Meta:
        fields = ("team", "level", "creation_date", "modified_date")
        model = TeamPermission


class UserPermissionListSerializer(serializers.ListSerializer[UserPermission]):
    child = UserPermissionSerializer()


class TeamPermissionListSerializer(serializers.ListSerializer[TeamPermission]):
    child = TeamPermissionSerializer()
