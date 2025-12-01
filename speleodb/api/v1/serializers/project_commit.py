# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import serializers

from frontend_private.templatetags.filter_utils import time_struct_since
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit


class ProjectCommitSerializer(serializers.ModelSerializer[ProjectCommit]):
    dt_since = serializers.SerializerMethodField()
    formats = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    authored_date = serializers.DateTimeField(format="%Y/%m/%d %H:%M")

    class Meta:
        model = ProjectCommit
        fields = [
            "id",
            "author_name",
            "author_email",
            "authored_date",
            "dt_since",
            "formats",
            "message",
            "parent_ids",
            "tree",
            "url",
        ]
        read_only_fields = fields  # all fields read-only for safety

    def get_url(self, obj: ProjectCommit) -> str | None:
        project = obj.project
        return reverse(
            "private:project_revision_explorer",
            kwargs={"project_id": project.id, "hexsha": obj.id},
        )

    def get_dt_since(self, obj: ProjectCommit) -> str:
        return time_struct_since(obj.authored_date.timetuple())

    def get_formats(self, obj: ProjectCommit) -> list[dict[str, Any]]:
        project: Project = obj.project

        if not isinstance(project, Project):
            raise ValidationError(
                f"Received unknown type for `project`: `{type(project)}`, "
                "expected `Project`"
            )

        formats: list[FileFormat] = [
            dl_format.raw_format
            for dl_format in project.formats_downloadable
            if dl_format.creation_date.replace(microsecond=0) <= obj.authored_date
        ]

        # all commits can be downloaded as a zip-file
        formats.append(FileFormat.DUMP)

        return [
            {
                "name": (
                    dl_format.webname
                    if dl_format != FileFormat.DUMP
                    else "Everything (ZIP)"
                ),
                "download_url": reverse(
                    "api:v1:project-download-at-hash",
                    kwargs={
                        "id": project.id,
                        "hexsha": obj.id,
                        "fileformat": dl_format.label.lower(),
                    },
                ),
            }
            for dl_format in formats
        ]
