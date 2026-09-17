"""Metadata stays small; authenticated details carry the editable geometry."""

from __future__ import annotations

from typing import Any
from typing import ClassVar

from rest_framework import serializers

from speleodb.common.enums import ColorPalette
from speleodb.common.enums import PermissionLevel
from speleodb.gis.geometry_services import create_gis_geometry
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISGeometryUserPermission
from speleodb.utils.serializer_fields import CustomChoiceField
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin


class GISGeometryListSerializer(
    SanitizedFieldsMixin,
    serializers.ModelSerializer[GISGeometry],
):
    sanitized_fields: ClassVar[list[str]] = ["name"]
    geometry_type = serializers.SerializerMethodField()
    user_permission_level = serializers.IntegerField(read_only=True, required=False)
    user_permission_level_label = serializers.SerializerMethodField()
    can_write = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    can_manage_permissions = serializers.SerializerMethodField()

    class Meta:
        model = GISGeometry
        fields = [
            "id",
            "name",
            "color",
            "created_by",
            "geometry_type",
            "revision",
            "user_permission_level",
            "user_permission_level_label",
            "can_write",
            "can_delete",
            "can_manage_permissions",
            "creation_date",
            "modified_date",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "geometry_type",
            "revision",
            "creation_date",
            "modified_date",
        ]

    def get_geometry_type(self, obj: GISGeometry) -> str:
        listed_type: str | None = getattr(obj, "listed_geometry_type", None)
        return listed_type if listed_type is not None else obj.geometry_type

    def _permission_level(self, obj: GISGeometry) -> int | None:
        return getattr(obj, "user_permission_level", None)

    def get_user_permission_level_label(self, obj: GISGeometry) -> str | None:
        level: int | None = self._permission_level(obj)
        return None if level is None else str(PermissionLevel.from_value(level).label)

    def get_can_write(self, obj: GISGeometry) -> bool:
        level: int | None = self._permission_level(obj)
        return level is not None and level >= PermissionLevel.READ_AND_WRITE

    def get_can_delete(self, obj: GISGeometry) -> bool:
        level: int | None = self._permission_level(obj)
        return level is not None and level >= PermissionLevel.ADMIN

    def get_can_manage_permissions(self, obj: GISGeometry) -> bool:
        return self.get_can_delete(obj)

    def validate_color(self, value: str) -> str:
        value = value.strip()
        if not ColorPalette.is_valid_hex(value):
            raise serializers.ValidationError(
                "Color must be a valid hex color (e.g. #e41a1c)"
            )
        return value.lower()


class GISGeometrySerializer(GISGeometryListSerializer):
    bbox_area_m2 = serializers.FloatField(read_only=True)
    vertex_count = serializers.IntegerField(read_only=True)

    class Meta(GISGeometryListSerializer.Meta):
        fields = [
            *GISGeometryListSerializer.Meta.fields,
            "geojson",
            "bbox_area_m2",
            "vertex_count",
        ]

    def create(self, validated_data: dict[str, Any]) -> GISGeometry:
        return create_gis_geometry(
            GISGeometry(**validated_data), self.context["request"].user
        )


class GISGeometryUpdateSerializer(GISGeometrySerializer):
    expected_revision = serializers.IntegerField(min_value=1, write_only=True)

    class Meta(GISGeometrySerializer.Meta):
        fields = [*GISGeometrySerializer.Meta.fields, "expected_revision"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if "expected_revision" not in attrs:
            raise serializers.ValidationError(
                {"expected_revision": "Load the saved geometry before updating it."}
            )
        return attrs


class GISGeometryUserPermissionSerializer(
    serializers.ModelSerializer[GISGeometryUserPermission]
):
    user = serializers.SlugRelatedField(read_only=True, slug_field="email")  # type: ignore[var-annotated]
    level = CustomChoiceField(PermissionLevel.choices_no_webviewer)

    class Meta:
        model = GISGeometryUserPermission
        fields = ("user", "level", "creation_date", "modified_date")
        read_only_fields = ("user", "creation_date", "modified_date")
