# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any
from typing import ClassVar

from rest_framework import serializers

from speleodb.common.enums import ColorPalette
from speleodb.gis.models import GPSTrack
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin


class GPSTrackSerializer(SanitizedFieldsMixin, serializers.ModelSerializer[GPSTrack]):
    sanitized_fields: ClassVar[list[str]] = ["name"]

    class Meta:
        model = GPSTrack
        fields = ["id", "name", "color", "creation_date", "modified_date"]

    def validate_color(self, value: str) -> str:
        """Ensure color is a valid 7-character hex code."""
        value = value.strip()
        if not ColorPalette.is_valid_hex(value):
            raise serializers.ValidationError(
                "Color must be a valid hex color (e.g. #e41a1c)"
            )
        return value.lower()

    def update(self, instance: GPSTrack, validated_data: Any) -> GPSTrack:
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        update_fields = list(validated_data.keys())
        if update_fields and "modified_date" not in update_fields:
            update_fields.append("modified_date")
        instance.save(update_fields=update_fields or None)
        return instance


class GPSTrackWithFileSerializer(serializers.ModelSerializer[GPSTrack]):
    file = serializers.SerializerMethodField()

    class Meta:
        model = GPSTrack
        fields = [
            "id",
            "name",
            "color",
            "file",
            "sha256_hash",
            "creation_date",
            "modified_date",
        ]
        read_only_fields = fields

    def get_file(self, obj: GPSTrack) -> str:
        """
        Retrieve the signed URL for the GeoJSON file
        """
        return obj.get_signed_download_url()
