# -*- coding: utf-8 -*-

from __future__ import annotations

from django.db.models import QuerySet
from rest_framework import serializers

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import ExperimentUserPermission
from speleodb.surveys.models import TeamProjectPermission
from speleodb.surveys.models import UserProjectPermission
from speleodb.utils.serializer_fields import CustomChoiceField


class ProjectUserPermissionSerializer(
    serializers.ModelSerializer[UserProjectPermission]
):
    user = serializers.SlugRelatedField(
        read_only=True,
        source="target",
        slug_field="email",
    )  # type: ignore[var-annotated]
    level = CustomChoiceField(PermissionLevel.choices)

    class Meta:
        fields = ("user", "level", "creation_date", "modified_date")
        model = UserProjectPermission


class ProjectTeamPermissionSerializer(
    serializers.ModelSerializer[TeamProjectPermission]
):
    team = serializers.PrimaryKeyRelatedField(read_only=True, source="target")  # type: ignore[var-annotated]
    level = CustomChoiceField(PermissionLevel.choices_no_admin)

    class Meta:
        fields = ("team", "level", "creation_date", "modified_date")
        model = TeamProjectPermission


class ProjectUserPermissionListSerializer(
    serializers.ListSerializer[UserProjectPermission]
):
    child = ProjectUserPermissionSerializer()


class ProjectTeamPermissionListSerializer(
    serializers.ListSerializer[TeamProjectPermission]
):
    child = ProjectTeamPermissionSerializer()


class ExperimentUserPermissionSerializer(
    serializers.ModelSerializer[ExperimentUserPermission]
):
    user = serializers.SlugRelatedField(read_only=True, slug_field="email")  # type: ignore[var-annotated]
    level = CustomChoiceField(PermissionLevel.choices_no_webviewer)

    class Meta:
        fields = ("user", "level", "creation_date", "modified_date")
        model = ExperimentUserPermission


class ExperimentUserPermissionListSerializer(
    serializers.ListSerializer[QuerySet[ExperimentUserPermission]]
):
    child = ExperimentUserPermissionSerializer()
