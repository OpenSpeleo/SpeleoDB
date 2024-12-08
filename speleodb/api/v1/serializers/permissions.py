#!/usr/bin/env python
# -*- coding: utf-8 -*-

from rest_framework import serializers

from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.utils.serializer_fields import CustomChoiceField


class UserPermissionSerializer(serializers.ModelSerializer):
    target = serializers.StringRelatedField()
    level = CustomChoiceField(choices=UserPermission.Level, source="_level")

    class Meta:
        fields = ("target", "level", "creation_date", "modified_date")
        model = UserPermission


class TeamPermissionSerializer(serializers.ModelSerializer):
    target = serializers.StringRelatedField()
    level = CustomChoiceField(choices=UserPermission.Level, source="_level")

    class Meta:
        fields = ("target", "level", "creation_date", "modified_date")
        model = TeamPermission


class UserPermissionListSerializer(serializers.ListSerializer):
    child = UserPermissionSerializer()


class TeamPermissionListSerializer(serializers.ListSerializer):
    child = TeamPermissionSerializer()
