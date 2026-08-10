# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any
from typing import ClassVar

from rest_framework import serializers

from speleodb.common.enums import ColorPalette
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import GPSTrackUserPermission
from speleodb.utils.serializer_fields import CustomChoiceField
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin


class GPSTrackSerializer(SanitizedFieldsMixin, serializers.ModelSerializer[GPSTrack]):
    sanitized_fields: ClassVar[list[str]] = ["name"]

    owner_email = serializers.EmailField(source="user.email", read_only=True)
    user_permission_level = serializers.IntegerField(read_only=True, required=False)
    user_permission_level_label = serializers.SerializerMethodField()
    can_write = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = GPSTrack
        fields = [
            "id",
            "name",
            "color",
            "owner_email",
            "user_permission_level",
            "user_permission_level_label",
            "can_write",
            "can_delete",
            "creation_date",
            "modified_date",
        ]
        read_only_fields = [
            "id",
            "owner_email",
            "user_permission_level",
            "user_permission_level_label",
            "can_write",
            "can_delete",
            "creation_date",
            "modified_date",
        ]

    def get_user_permission_level_label(self, obj: GPSTrack) -> str | None:
        level = getattr(obj, "user_permission_level", None)
        if level is None:
            return None
        return str(PermissionLevel.from_value(level).label)

    def get_can_write(self, obj: GPSTrack) -> bool:
        level = getattr(obj, "user_permission_level", None)
        return level is not None and level >= PermissionLevel.READ_AND_WRITE

    def get_can_delete(self, obj: GPSTrack) -> bool:
        level = getattr(obj, "user_permission_level", None)
        return level is not None and level >= PermissionLevel.ADMIN

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


class GPSTrackWithFileSerializer(GPSTrackSerializer):
    file = serializers.SerializerMethodField()

    class Meta(GPSTrackSerializer.Meta):
        fields = [*GPSTrackSerializer.Meta.fields, "file", "sha256_hash"]
        read_only_fields = fields

    def get_file(self, obj: GPSTrack) -> str:
        """
        Retrieve the signed URL for the GeoJSON file
        """
        return obj.get_signed_download_url()


class GPSTrackUserPermissionSerializer(
    serializers.ModelSerializer[GPSTrackUserPermission]
):
    user = serializers.SlugRelatedField(read_only=True, slug_field="email")  # type: ignore[var-annotated]
    level = CustomChoiceField(PermissionLevel.choices_no_webviewer)

    class Meta:
        model = GPSTrackUserPermission
        fields = ("user", "level", "creation_date", "modified_date")
        read_only_fields = ("user", "creation_date", "modified_date")
