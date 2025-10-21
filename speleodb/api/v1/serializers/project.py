# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

from django_countries import countries
from rest_framework import serializers

from speleodb.surveys.models import GeoJSON
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Project
from speleodb.surveys.models import UserPermission
from speleodb.users.models import User
from speleodb.utils.exceptions import NotAuthorizedError
from speleodb.utils.serializer_fields import CustomChoiceField


def format_coordinate(value: Any) -> float:
    """Format a coordinate value to 7 decimal places"""
    return round(float(value), 7)


class ProjectSerializer(serializers.ModelSerializer[Project]):
    country = CustomChoiceField(choices=list(countries))
    visibility = CustomChoiceField(
        choices=Project.Visibility,  # type: ignore[arg-type]
        default=Project.Visibility.PRIVATE,
    )

    permission = serializers.SerializerMethodField()
    active_mutex = serializers.SerializerMethodField()

    n_commits = serializers.SerializerMethodField()

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
            data["latitude"] = format_coordinate(latitude)
            data["longitude"] = format_coordinate(longitude)

        return super().to_internal_value(data)

    def to_representation(self, instance: Project) -> dict[str, Any]:
        """Ensure coordinates are rounded to 7 decimal places."""
        data = super().to_representation(instance)

        if data.get("latitude") is not None:
            data["latitude"] = format_coordinate(data["latitude"])
        else:
            del data["latitude"]

        if data.get("longitude") is not None:
            data["longitude"] = format_coordinate(data["longitude"])
        else:
            del data["longitude"]

        if data.get("n_commits") is None:
            del data["n_commits"]

        if data.get("permission") is None:
            del data["permission"]

        return data

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
            target=User.objects.get(email=validated_data["created_by"]),
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

        user: User | None = self.context.get("user")  # pyright: ignore[reportAssignmentType]

        if user is None:
            return None

        try:
            return str(user.get_best_permission(project=obj).level_label)

        except NotAuthorizedError:
            return None

    def get_active_mutex(self, obj: Project) -> dict[str, Any] | None:
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


class ProjectGeoJSONFileSerializer(serializers.ModelSerializer[GeoJSON]):
    date = serializers.DateTimeField(source="commit_date")
    url = serializers.CharField(source="get_signed_download_url", read_only=True)

    class Meta:
        model = GeoJSON
        fields = ["commit_sha", "date", "url"]
        read_only_fields = ["__all__"]


class ProjectWithGeoJsonSerializer(ProjectSerializer):
    geojson_files = serializers.SerializerMethodField()

    class Meta(ProjectSerializer.Meta):
        read_only_fields = ["__all__"]

    def get_geojson_files(self, obj: Project) -> dict[str, str]:
        """
        Retrieve geojson files from serializer context.
        Expect the context to have a 'geojson_files' key containing
        a queryset or list of GeoJson instances.
        """
        if hasattr(obj, "_geojson_files"):
            geojson_qs = obj._geojson_files  # noqa: SLF001  # type: ignore[attr-defined]

        else:
            geojson_qs = obj.rel_geojsons

        return ProjectGeoJSONFileSerializer(
            geojson_qs, many=True, context=self.context
        ).data
