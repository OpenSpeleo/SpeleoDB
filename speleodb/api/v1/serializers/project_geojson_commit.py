# -*- coding: utf-8 -*-

from __future__ import annotations

from rest_framework import serializers

from speleodb.gis.models import ProjectGeoJSON


class ProjectGeoJSONCommitSerializer(serializers.ModelSerializer[ProjectGeoJSON]):
    """
    Lightweight serializer for ProjectGeoJSON commit metadata.

    Used for populating commit selection dropdowns in UIs.
    Does not include signed URLs or file data.
    """

    commit_sha = serializers.CharField(source="commit.id", read_only=True)
    commit_date = serializers.DateTimeField(
        source="commit.authored_date", read_only=True
    )
    commit_author_name = serializers.CharField(
        source="commit.author_name", read_only=True
    )
    commit_author_email = serializers.EmailField(
        source="commit.author_email", read_only=True
    )
    commit_message = serializers.CharField(source="commit.message", read_only=True)

    class Meta:
        model = ProjectGeoJSON
        fields = [
            "commit_sha",
            "commit_date",
            "commit_author_name",
            "commit_author_email",
            "commit_message",
        ]
        read_only_fields = ["__all__"]
