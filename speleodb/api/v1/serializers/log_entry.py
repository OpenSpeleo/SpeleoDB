# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from speleodb.gis.models import LogEntry


class LogEntrySerializer(serializers.ModelSerializer[LogEntry]):
    """Serializer for LogEntry model."""

    class Meta:
        model = LogEntry
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
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            if file_field.size > max_size:
                raise serializers.ValidationError(
                    {"file": "File size cannot exceed 5MB."}
                )

        return attrs
