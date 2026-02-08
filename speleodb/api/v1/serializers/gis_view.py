# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import Any
from typing import ClassVar

from rest_framework import serializers

from speleodb.gis.models import GISProjectView
from speleodb.gis.models import GISView
from speleodb.surveys.models import Project
from speleodb.utils.exceptions import NotAuthorizedError
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin

sha1_regex = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


class GISProjectViewSerializer(serializers.ModelSerializer[GISProjectView]):
    """Serializer for GISProjectView (read operations)."""

    project_id = serializers.UUIDField(source="project.id", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = GISProjectView
        fields = [
            "id",
            "project_id",
            "project_name",
            "commit_sha",
            "use_latest",
            "creation_date",
        ]
        read_only_fields = ["id", "project_id", "project_name", "creation_date"]


class GISProjectViewInputSerializer(serializers.Serializer[GISProjectView]):
    """Serializer for project input when creating/updating GIS views."""

    project_id = serializers.UUIDField()
    commit_sha = serializers.CharField(
        max_length=40,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    use_latest = serializers.BooleanField(default=False)

    def validate_commit_sha(self, value: str | None) -> str | None:
        """Validate commit SHA format."""

        if value:
            value = value.strip().lower()
            if not bool(sha1_regex.fullmatch(value)):
                raise serializers.ValidationError("Commit SHA is not valid")

        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate that either use_latest or commit_sha is provided."""
        use_latest = attrs.get("use_latest", False)
        commit_sha = attrs.get("commit_sha", None)  # noqa: SIM910

        if not use_latest and not commit_sha:
            raise serializers.ValidationError(
                "Either use_latest must be true or commit_sha must be provided"
            )

        return attrs


class GISViewSerializer(serializers.ModelSerializer[GISView]):
    """Serializer for GIS View (read operations)."""

    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    project_count = serializers.SerializerMethodField()
    projects = GISProjectViewSerializer(
        source="project_views",
        many=True,
        read_only=True,
    )

    class Meta:
        model = GISView
        fields = [
            "id",
            "name",
            "description",
            "allow_precise_zoom",
            "gis_token",
            "owner_email",
            "project_count",
            "projects",
            "creation_date",
            "modified_date",
        ]
        read_only_fields = [
            "id",
            "gis_token",
            "owner_email",
            "creation_date",
            "modified_date",
            "project_count",
        ]

    def get_project_count(self, obj: GISView) -> int:
        """Get the number of projects in this view."""
        return obj.project_views.count()


class GISViewCreateUpdateSerializer(
    SanitizedFieldsMixin, serializers.ModelSerializer[GISView]
):
    """Serializer for creating/updating GIS views."""

    sanitized_fields: ClassVar[list[str]] = ["name", "description"]

    projects = GISProjectViewInputSerializer(many=True, write_only=True)

    class Meta:
        model = GISView
        fields = [
            "name",
            "description",
            "allow_precise_zoom",
            "projects",
        ]

    def validate_projects(
        self, projects_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Validate projects exist and user has access."""
        user = self.context.get("user")
        if not user:
            raise serializers.ValidationError("User context required")

        # Check for duplicate projects in input
        project_ids = [p["project_id"] for p in projects_data]
        if len(project_ids) != len(set(project_ids)):
            raise serializers.ValidationError("Duplicate projects not allowed")

        # Validate each project

        validated_projects = []
        for project_data in projects_data:
            project_id = project_data["project_id"]

            try:
                project = Project.objects.get(id=project_id, is_active=True)
            except Project.DoesNotExist as e:
                raise serializers.ValidationError(
                    f"Project {project_id} does not exist or is not active"
                ) from e

            # Check user has at least read access
            try:
                user.get_best_permission(project)
            except NotAuthorizedError as e:
                raise serializers.ValidationError(
                    f"You do not have access to project {project.name}"
                ) from e

            validated_projects.append(project_data)

        return validated_projects

    def create(self, validated_data: dict[str, Any]) -> GISView:
        """Create a new GIS view with associated projects."""
        projects_data = validated_data.pop("projects", [])
        user = self.context["user"]

        # Create the GIS view
        gis_view = GISView.objects.create(
            owner=user,
            **validated_data,
        )

        # Create project associations
        for project_data in projects_data:
            GISProjectView.objects.create(
                gis_view=gis_view,
                project_id=project_data["project_id"],
                commit_sha=project_data.get("commit_sha"),
                use_latest=project_data.get("use_latest", False),
            )

        return gis_view

    def update(self, instance: GISView, validated_data: dict[str, Any]) -> GISView:
        """Update GIS view and replace project associations."""
        projects_data = validated_data.pop("projects", None)

        # Update basic fields
        instance.name = validated_data.get("name", instance.name)
        instance.description = validated_data.get("description", instance.description)
        instance.allow_precise_zoom = validated_data.get(
            "allow_precise_zoom", instance.allow_precise_zoom
        )
        instance.save()

        # Replace projects if provided
        if projects_data is not None:
            # Delete existing associations
            instance.project_views.all().delete()

            # Create new associations
            for project_data in projects_data:
                GISProjectView.objects.create(
                    gis_view=instance,
                    project_id=project_data["project_id"],
                    commit_sha=project_data.get("commit_sha"),
                    use_latest=project_data.get("use_latest", False),
                )

        return instance

    def to_representation(self, instance: GISView) -> dict[str, Any]:
        """Use the read serializer for output."""
        serializer = GISViewSerializer(instance, context=self.context)
        return serializer.data


class GISViewDataGeoJSONFileSerializer(serializers.Serializer[Any]):
    """Serializer for individual GeoJSON file in GIS view data response."""

    project_id = serializers.UUIDField()
    project_name = serializers.CharField()
    commit_sha = serializers.CharField()
    commit_date = serializers.CharField()  # ISO format string
    url = serializers.URLField()
    use_latest = serializers.BooleanField()


class PublicGISProjectViewSerializer(serializers.Serializer[dict[str, Any]]):
    """Serializer for individual project in public GIS view frontend response."""

    id = serializers.UUIDField(source="project_id")
    name = serializers.CharField(source="project_name")
    geojson_file = serializers.SerializerMethodField()
    commit_sha = serializers.CharField()
    commit_date = serializers.CharField()
    use_latest = serializers.BooleanField()

    def get_geojson_file(self, obj: dict[str, Any]) -> str | None:
        """Extract URL from tuple if needed."""
        url = obj.get("url", None)  # noqa: SIM910

        match url:
            case str():
                return url
            case _:
                return None


class PublicGISViewSerializer(serializers.Serializer[GISView]):
    """
    Serializer for the public GIS view frontend map viewer response.

    Used by the public SpeleoDB map viewer at /view/<gis_token>/
    Returns data in a format suitable for the frontend JavaScript.
    """

    view_name = serializers.CharField(source="name")
    view_description = serializers.CharField(source="description")
    allow_precise_zoom = serializers.BooleanField()
    projects = serializers.SerializerMethodField()

    def get_projects(self, obj: GISView) -> list[dict[str, Any]]:
        """Get projects with signed GeoJSON URLs."""
        expires_in = self.context.get("expires_in", 3600)
        try:
            geojson_data = obj.get_geojson_urls(expires_in=expires_in)
            serializer = PublicGISProjectViewSerializer(geojson_data, many=True)  # type: ignore[arg-type]
            return serializer.data  # type: ignore[return-value]
        except Exception:  # noqa: BLE001
            return []


class GISViewDataSerializer(serializers.Serializer[GISView]):
    """
    Serializer for the public GIS view data endpoint response.

    Used by external GIS tools to get signed URLs for GeoJSON files.
    """

    view_id = serializers.SerializerMethodField()
    view_name = serializers.CharField(source="name")
    description = serializers.CharField()
    allow_precise_zoom = serializers.BooleanField()
    geojson_files = serializers.SerializerMethodField()

    def get_view_id(self, obj: GISView) -> str:
        """Return view ID as string."""
        return str(obj.id)

    def get_geojson_files(self, obj: GISView) -> list[dict[str, Any]]:
        """Get signed URLs for all projects in the view."""
        expires_in = self.context.get("expires_in", 3600)
        try:
            geojson_data = obj.get_geojson_urls(expires_in=expires_in)
            # Use the GeoJSON file serializer for consistent structure
            serializer = GISViewDataGeoJSONFileSerializer(geojson_data, many=True)
            return serializer.data  # type: ignore[return-value]
        except Exception:  # noqa: BLE001
            # Return empty list on error (logged in view)
            return []
