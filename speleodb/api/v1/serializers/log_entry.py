# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any
from typing import ClassVar

from django.conf import settings
from rest_framework import serializers

from speleodb.gis.models import StationLogEntry
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin


class StationLogEntrySerializer(
    SanitizedFieldsMixin, serializers.ModelSerializer[StationLogEntry]
):
    """Serializer for StationLogEntry model."""

    sanitized_fields: ClassVar[list[str]] = ["title", "notes"]

    class Meta:
        model = StationLogEntry
        fields = [
            "id",
            "attachment",
            "created_by",
            "creation_date",
            "modified_date",
            "notes",
            "station",
            "title",
        ]

        read_only_fields = [
            "id",
            "created_by",
            "creation_date",
            "modified_date",
            "station",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate that file-based resources have files and text-based have text."""
        # Get resource_type - if updating, use existing if not provided
        file_field = attrs.get("attachment")

        # Validate file size (max 5MBs)
        if file_field:
            max_size = settings.DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT * 1024 * 1024
            if file_field.size > max_size:
                raise serializers.ValidationError(
                    {"file": "File size cannot exceed 5MB."}
                )

        return attrs
