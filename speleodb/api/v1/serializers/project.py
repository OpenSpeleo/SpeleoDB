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


class UserField(serializers.RelatedField):
    def to_representation(self, value):
        return value.email

    def to_internal_value(self, data):
        if isinstance(data, User):
            return data
        return User.objects.get(email=data)


class ProjectSerializer(serializers.ModelSerializer):
    country = CustomChoiceField(choices=countries)
    visibility = CustomChoiceField(
        choices=Project.Visibility,
        source="_visibility",
        default=Project.Visibility.PRIVATE,
    )

    permission = serializers.SerializerMethodField()
    active_mutex = serializers.SerializerMethodField()

    n_commits = serializers.SerializerMethodField()

    created_by = UserField(queryset=User.objects.all())

    class Meta:
        model = Project
        exclude = ("_visibility",)

    def create(self, validated_data: dict) -> Project:
        project = super().create(validated_data)

        # assign an ADMIN permission to the creator
        _ = UserPermission.objects.create(
            project=project,
            target=validated_data["created_by"],
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

    def get_n_commits(self, obj: Project) -> int | None:
        # Check if the condition to include the expensive field is met
        if self.context.get("n_commits", False):
            # return len(obj.commit_history)
            return obj.git_repo.commit_count
        return None
