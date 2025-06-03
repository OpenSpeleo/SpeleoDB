#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime  # noqa: TC003
import decimal
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django_countries import countries
from rest_framework import serializers

from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Project
from speleodb.surveys.models import UserPermission
from speleodb.users.models import User
from speleodb.utils.serializer_fields import CustomChoiceField


class UserField(serializers.RelatedField[User, User, str]):
    def to_representation(self, value: User) -> str:
        return value.email

    def to_internal_value(self, data: User | str) -> User:
        match data:
            case User():
                return data
            case str():
                return User.objects.get(email=data)
            case _:
                raise TypeError


class ProjectSerializer(serializers.ModelSerializer[Project]):
    country = CustomChoiceField(choices=list(countries))
    visibility = CustomChoiceField(
        choices=Project.Visibility,  # type: ignore[arg-type]
        default=Project.Visibility.PRIVATE,
    )

    permission = serializers.SerializerMethodField()
    active_mutex = serializers.SerializerMethodField()

    n_commits = serializers.SerializerMethodField()

    created_by = UserField(queryset=User.objects.all(), required=False)

    class Meta:
        model = Project
        fields = "__all__"

    def to_internal_value(self, data: Any) -> Any:
        latitude = data.get("latitude", None)
        longitude = data.get("longitude", None)

        if (
            latitude is not None
            and latitude != ""
            and longitude is not None
            and longitude != ""
        ):
            data["latitude"] = str(round(decimal.Decimal(latitude), 8))
            data["longitude"] = str(round(decimal.Decimal(longitude), 8))

        return super().to_internal_value(data)

    def validate(self, attrs: Any) -> Any:
        latitude = attrs.get("latitude", None)
        longitude = attrs.get("longitude", None)
        created_by = attrs.get("created_by", None)

        if self.instance is None and created_by is None:
            raise serializers.ValidationError(
                "`created_by` must be specified during creation."
            )

        if self.instance is not None and "created_by" in attrs:
            raise serializers.ValidationError("`created_by` cannot be updated.")

        if (longitude is None) != (latitude is None) or (longitude != "") != (
            latitude != ""
        ):
            raise serializers.ValidationError(
                "`latitude` and `longitude` must be simultaneously specified or empty"
            )

        return attrs

    def create(self, validated_data: Any) -> Project:
        project = super().create(validated_data)

        # assign an ADMIN permission to the creator
        _ = UserPermission.objects.create(
            project=project,
            target=validated_data["created_by"],
            level=PermissionLevel.ADMIN,
        )

        return project

    def update(self, instance: Project, validated_data: Any) -> Project:
        validated_data.pop("created_by", None)  # Remove created_by if present

        return super().update(instance, validated_data)

    def get_permission(self, obj: Project) -> str | None:
        if isinstance(obj, dict):
            # Unsaved object
            return None

        user = self.context.get("user")

        if user is None:
            return None

        try:
            return str(obj.get_best_permission(user=user).level_label)
        except ObjectDoesNotExist:
            return None

    def get_active_mutex(
        self, obj: Project
    ) -> dict[str, str | datetime.datetime] | None:
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
