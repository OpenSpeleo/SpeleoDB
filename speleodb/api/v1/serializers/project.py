#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime

from django.core.exceptions import ObjectDoesNotExist
from django_countries import countries
from rest_framework import serializers

from speleodb.surveys.models import Project
from speleodb.surveys.models import UserPermission
from speleodb.users.models import User
from speleodb.utils.serializer_fields import CustomChoiceField


class ProjectSerializer(serializers.ModelSerializer):
    country = CustomChoiceField(choices=countries)
    visibility = CustomChoiceField(
        choices=Project.Visibility,
        source="_visibility",
        default=Project.Visibility.PRIVATE,
    )

    permission = serializers.SerializerMethodField()
    active_mutex = serializers.SerializerMethodField()

    created_by = serializers.EmailField()

    class Meta:
        model = Project
        exclude = ("_visibility",)

    def create(self, validated_data: dict) -> Project:
        validated_data["created_by"] = User.objects.get(
            email=validated_data["created_by"]
        )

        project = super().create(validated_data)

        # assign current user as project admin
        UserPermission.objects.create(
            project=project,
            target=self.context.get("user"),
            level=UserPermission.Level.ADMIN,
        )

        return project

    def get_permission(self, obj: Project) -> str:
        if isinstance(obj, dict):
            # Unsaved object
            return None

        user = self.context.get("user")

        try:
            return obj.get_best_permission(user=user).level
        except ObjectDoesNotExist:
            return None

    def get_active_mutex(self, obj: Project) -> dict[str, str | datetime.datetime]:
        if isinstance(obj, dict):
            # Unsaved object
            return None

        if obj.active_mutex is None:
            return None

        return {
            "user": obj.active_mutex.user.email,
            "creation_date": obj.active_mutex.creation_date,
            "modified_date": obj.active_mutex.modified_date,
        }
