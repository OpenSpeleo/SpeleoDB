# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from decimal import InvalidOperation
from typing import Any

from django_countries import countries
from rest_framework import serializers

# from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError

from speleodb.api.v1.serializers.project_commit import ProjectCommitSerializer
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectType
from speleodb.surveys.models import ProjectVisibility
from speleodb.surveys.models import UserProjectPermission
from speleodb.users.models import User
from speleodb.utils.exceptions import NotAuthorizedError
from speleodb.utils.gps_utils import format_coordinate
from speleodb.utils.gps_utils import maybe_convert_dms_to_decimal
from speleodb.utils.serializer_fields import CustomChoiceField


class ProjectSerializer(serializers.ModelSerializer[Project]):
    country = CustomChoiceField(choices=list(countries))
    visibility = CustomChoiceField(
        choices=ProjectVisibility,  # type: ignore[arg-type]
        default=ProjectVisibility.PRIVATE,
    )

    commit_count = serializers.SerializerMethodField()
    latest_commit = serializers.SerializerMethodField()

    permission = serializers.SerializerMethodField()
    active_mutex = serializers.SerializerMethodField()

    created_by = serializers.CharField(required=False)

    n_commits = serializers.SerializerMethodField()

    type = CustomChoiceField(choices=ProjectType, required=True)  # type: ignore[arg-type]

    class Meta:
        model = Project
        fields = "__all__"

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

    def to_internal_value(self, data: dict[str, Any]) -> Any:
        """Override to round coordinates before validation."""

        # Data is immutable - need to copy
        data = data.copy()

        if latitude := data.get("latitude", ""):
            if isinstance(latitude, str):
                # Remove both degree and white space
                latitude = latitude.strip(" °")

                if any(quadrant in latitude.upper() for quadrant in ["E", "W"]):
                    raise ValidationError(
                        {
                            "latitude": [
                                f"Invalid quadrant received: `{latitude}`. [N, S] only"
                            ]
                        }
                    )

                latitude = maybe_convert_dms_to_decimal(latitude)

            with contextlib.suppress(ValueError, TypeError, InvalidOperation):
                # Let the field validation handle the error
                data["latitude"] = format_coordinate(latitude)

        if longitude := data.get("longitude", ""):
            if isinstance(longitude, str):
                # Remove both degree and white space
                longitude = longitude.strip(" °")

                if any(quadrant in longitude.upper() for quadrant in ["N", "S"]):
                    raise ValidationError(
                        {
                            "longitude": [
                                f"Invalid quadrant received: `{longitude}`. [E, W] only"
                            ]
                        }
                    )

                longitude = maybe_convert_dms_to_decimal(longitude)

            with contextlib.suppress(ValueError, TypeError, InvalidOperation):
                # Let the field validation handle the error
                data["longitude"] = format_coordinate(longitude)

        return super().to_internal_value(data)

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        created_by = attrs.get("created_by")

        if self.instance is None and created_by is None:
            raise serializers.ValidationError(
                "`created_by` must be specified during creation."
            )

        if self.instance is not None and "created_by" in attrs:
            raise serializers.ValidationError("`created_by` cannot be updated.")

        # Guarantee that even a None value ends up `""`
        latitude = attrs.get("latitude", "") or ""
        longitude = attrs.get("longitude", "") or ""

        if (longitude == "") != (latitude == ""):
            raise serializers.ValidationError(
                "`latitude` and `longitude` must be simultaneously specified or empty"
            )

        return attrs

    def create(self, validated_data: Any) -> Project:
        project = super().create(validated_data)

        # assign an ADMIN permission to the creator
        _ = UserProjectPermission.objects.create(
            project=project,
            target=User.objects.get(email=validated_data["created_by"]),
            level=PermissionLevel.ADMIN,
        )

        return project

    def update(self, instance: Project, validated_data: Any) -> Project:
        validated_data.pop("created_by", None)  # Remove created_by if present

        return super().update(instance, validated_data)

    def get_permission(self, obj: Project | dict[str, Any]) -> str | None:
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

        if (active_mtx := obj.active_mutex) is None:
            return None

        return {
            "user": active_mtx.user.email,
            "creation_date": active_mtx.creation_date,
            "modified_date": active_mtx.modified_date,
        }

    def get_n_commits(self, obj: Project) -> int | None:
        # Check if the condition to include the expensive field is met
        if self.context.get("n_commits", False):
            # return len(obj.commit_history)
            return obj.git_repo.commit_count
        return None

    def get_latest_commit(self, obj: Project) -> None | dict[str, str]:
        """
        Return the first commit in obj.commits (prefetch_related or default ordering).
        Returns None if there are no commits.
        """
        latest_commit = obj.latest_commit

        if latest_commit is None:
            return None

        return ProjectCommitSerializer(latest_commit).data

    def get_commit_count(self, obj: Project) -> int:
        """
        Return the total number of commits in the project.
        """
        return obj.commit_count


class ProjectGeoJSONFileSerializer(serializers.ModelSerializer[ProjectGeoJSON]):
    date = serializers.DateTimeField(source="commit_date")
    url = serializers.CharField(source="get_signed_download_url", read_only=True)

    class Meta:
        model = ProjectGeoJSON
        fields = [
            "commit_author_name",
            "commit_author_email",
            "commit_date",
            "commit_message",
            "commit_sha",
            "date",
            "url",
        ]
        read_only_fields = ["__all__"]


class ProjectWithGeoJsonSerializer(ProjectSerializer):
    geojson_file = serializers.SerializerMethodField()

    class Meta(ProjectSerializer.Meta):
        read_only_fields = ["__all__"]

    def get_geojson_file(self, obj: Project) -> str | None:
        """
        Retrieve geojson files from serializer context.
        Expect the context to have a 'geojson_files' key containing
        a queryset or list of GeoJson instances.
        """

        try:
            geojson_obj = obj.rel_geojsons.order_by("-commit_date")[0]
            return geojson_obj.get_signed_download_url()

        except IndexError:
            return None
