# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import serializers

from frontend_private.templatetags.filter_utils import format_byte_size
from frontend_private.templatetags.filter_utils import time_struct_since
from speleodb.git_engine.core import GitCommit
from speleodb.git_engine.core import GitFile
from speleodb.surveys.models import Format
from speleodb.surveys.models import Project


class GitCommitSerializer(serializers.Serializer[GitCommit]):
    """
    Serializer for Git Commit objects.
    """

    author_name = serializers.CharField(source="author.name")
    author_email = serializers.CharField(source="author.email")
    authored_date = serializers.DateTimeField(
        source="authored_datetime", format="%Y/%m/%d %H:%M"
    )

    committer_name = serializers.CharField(source="committer.name")
    committer_email = serializers.CharField(source="committer.email")

    committed_date = serializers.DateTimeField(
        source="committed_datetime", format="%Y/%m/%d %H:%M"
    )

    dt_since = serializers.SerializerMethodField()

    hexsha = serializers.CharField()
    hexsha_short = serializers.CharField()

    message = serializers.CharField()
    parents = serializers.ListField(child=serializers.CharField())
    url = serializers.SerializerMethodField()

    formats = serializers.SerializerMethodField()

    # ------------------------- Read-Only Serializer ------------------------ #

    def create(self, validated_data: Any) -> Any:
        raise serializers.ValidationError("This serializer is read-only.")

    def update(self, instance: Any, validated_data: Any) -> Any:
        raise serializers.ValidationError("This serializer is read-only.")

    # ------------------------- GitCommit Attributes ------------------------ #

    def get_formats(self, obj: GitCommit) -> list[dict[str, Any]]:
        """
        Returns the short version of the commit hash (7 characters by GitHub standard).
        """
        project: Project | None = self.context.get("project")
        if project is not None:
            if not isinstance(project, Project):
                raise ValidationError(
                    f"Received unknown type for `project`: `{type(project)}`, "
                    "expected `Project`"
                )

            # Matching the TZ of Git Commit which are on UTC
            commit_date = datetime.datetime.fromtimestamp(
                obj.authored_date, tz=datetime.UTC
            )

            formats: list[Format.FileFormat] = [
                dl_format.raw_format
                for dl_format in project.formats_downloadable
                if dl_format.creation_date.replace(microsecond=0) <= commit_date
            ]

            # all commits can be downloaded as a zip-file
            formats.append(Format.FileFormat.DUMP)

            return [
                {
                    "name": (
                        dl_format.webname
                        if dl_format != Format.FileFormat.DUMP
                        else "Everything (ZIP)"
                    ),
                    "download_url": reverse(
                        "api:v1:project-download-at-hash",
                        kwargs={
                            "id": project.id,
                            "hexsha": obj.hexsha,
                            "fileformat": dl_format.label.lower(),
                        },
                    ),
                }
                for dl_format in formats
            ]

        return []

    def get_url(self, obj: GitCommit) -> str | None:
        project: Project | None = self.context.get("project")
        if project is not None:
            return reverse(
                "private:project_revision_explorer",
                kwargs={"project_id": project.id, "hexsha": obj.hexsha},
            )
        return None

    def get_dt_since(self, obj: GitCommit) -> str:
        return time_struct_since(obj.date)

    def to_representation(self, instance: GitCommit) -> dict[str, Any]:
        """
        Custom representation logic for the commit object.
        - Includes the list of parent commit hashes.
        - Formats the authored and committed date-time fields.
        """
        representation = super().to_representation(instance)
        # Add additional fields or formatting if necessary.
        representation["parents"] = [parent.hexsha for parent in instance.parents]
        return representation


class GitCommitListSerializer(serializers.ListSerializer[GitCommit]):
    """
    Serializer for a list of Git Commit objects.
    """

    child = GitCommitSerializer()

    def to_representation(self, data: list[GitCommit]) -> list[Any]:  # type: ignore[override]
        """
        Customize the list serialization.
        """
        # Sort commits by date (descending) if needed
        return super().to_representation(
            sorted(data, key=lambda commit: commit.authored_datetime, reverse=True)
        )


class GitFileSerializer(serializers.Serializer[GitCommit]):
    """
    Serializer for GitFile objects.
    """

    name = serializers.CharField()
    hexsha = serializers.CharField()
    path = serializers.CharField()
    size = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    # # Commit aspects
    # commit_hexsha = serializers.CharField(source="commit.hexsha")
    # commit_message = serializers.CharField(source="commit.message")
    # commit_dt_since = serializers.SerializerMethodField()
    # commit_url = serializers.SerializerMethodField()
    commit = GitCommitSerializer()

    # ------------------------- Read-Only Serializer ------------------------ #

    def create(self, validated_data: Any) -> Any:
        raise serializers.ValidationError("This serializer is read-only.")

    def update(self, instance: Any, validated_data: Any) -> Any:
        raise serializers.ValidationError("This serializer is read-only.")

    # -------------------------- GitFile Attributes ------------------------- #

    def get_size(self, obj: GitFile) -> str:
        return format_byte_size(obj.size)

    def get_download_url(self, obj: GitFile) -> str | None:
        project: Project | None = self.context.get("project")
        if project is not None:
            return reverse(
                "api:v1:project-download-blob",
                kwargs={"id": project.id, "hexsha": obj.hexsha},
            )
        return None


class GitFileListSerializer(serializers.ListSerializer[GitFile]):
    """
    Serializer for a list of Git Commit objects.
    """

    child = GitFileSerializer()

    def to_representation(self, data: list[GitFile]) -> list[Any]:  # type: ignore[override]
        """
        Customize the list serialization.
        """
        # Sort commits by date (descending) if needed
        return super().to_representation(sorted(data, key=lambda file: file.path))
