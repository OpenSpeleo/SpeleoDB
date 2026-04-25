# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

from rest_framework import serializers

from speleodb.common.enums import ColorPalette
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission
from speleodb.users.models import User
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise


class LandmarkCollectionSerializer(
    SanitizedFieldsMixin, serializers.ModelSerializer[LandmarkCollection]
):
    """Serializer for LandmarkCollection model."""

    sanitized_fields: ClassVar[list[str]] = ["name", "description"]

    name = serializers.CharField(
        max_length=100,
        min_length=1,
        allow_blank=False,
        required=True,
        trim_whitespace=True,
    )
    created_by = serializers.EmailField(required=False)
    landmark_count = serializers.IntegerField(read_only=True, required=False, default=0)

    class Meta:
        model = LandmarkCollection
        fields = [
            "id",
            "name",
            "description",
            "color",
            "gis_token",
            "created_by",
            "collection_type",
            "personal_owner",
            "creation_date",
            "modified_date",
            "landmark_count",
        ]
        read_only_fields = [
            "id",
            "gis_token",
            "collection_type",
            "personal_owner",
            "creation_date",
            "modified_date",
            "landmark_count",
        ]

    def validate_name(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("Collection name cannot be empty.")
        return value.strip()

    def validate_color(self, value: str) -> str:
        """Ensure color is a valid 7-character hex code."""
        value = value.strip()
        if not ColorPalette.is_valid_hex(value):
            raise serializers.ValidationError(
                "Color must be a valid hex color (e.g. #377eb8)"
            )
        return value.lower()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        created_by = attrs.get("created_by")

        if self.instance is not None and "is_active" in self.initial_data:
            raise serializers.ValidationError(
                "`is_active` cannot be updated through this endpoint."
            )

        if self.instance is None and created_by is None:
            raise serializers.ValidationError(
                "`created_by` must be specified during creation."
            )

        if self.instance is not None and "created_by" in attrs:
            raise serializers.ValidationError("`created_by` cannot be updated.")

        return attrs

    def create(self, validated_data: dict[str, Any]) -> LandmarkCollection:
        validated_data["collection_type"] = LandmarkCollection.CollectionType.SHARED
        validated_data["personal_owner"] = None
        validated_data["is_active"] = True
        collection = super().create(validated_data)
        _ = LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=User.objects.get(email=validated_data["created_by"]),
            level=PermissionLevel.ADMIN,
        )
        return collection


class LandmarkCollectionWithPermSerializer(
    serializers.ModelSerializer[LandmarkCollection]
):
    """Optimized serializer for listing collections with user permission level."""

    landmark_count = serializers.IntegerField(read_only=True)
    user_permission_level = serializers.IntegerField(read_only=True, required=False)
    user_permission_level_label = serializers.SerializerMethodField()
    is_personal = serializers.SerializerMethodField()

    class Meta:
        model = LandmarkCollection
        fields = [
            "id",
            "name",
            "description",
            "color",
            "collection_type",
            "personal_owner",
            "is_personal",
            "gis_token",
            "created_by",
            "creation_date",
            "modified_date",
            "landmark_count",
            "user_permission_level",
            "user_permission_level_label",
        ]
        read_only_fields = fields

    def get_user_permission_level_label(
        self, obj: LandmarkCollection
    ) -> StrOrPromise | None:
        if perm_lvl := getattr(obj, "user_permission_level", None):
            return PermissionLevel.from_value(perm_lvl).label

        return None

    def get_is_personal(self, obj: LandmarkCollection) -> bool:
        return obj.is_personal


class LandmarkCollectionUserPermissionSerializer(
    serializers.ModelSerializer[LandmarkCollectionUserPermission]
):
    """Serializer for LandmarkCollectionUserPermission model."""

    user_email = serializers.EmailField(write_only=True, required=False)
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_full_name = serializers.SerializerMethodField()
    user_display_email = serializers.EmailField(source="user.email", read_only=True)
    level_label = serializers.CharField(read_only=True)
    collection_id = serializers.UUIDField(source="collection.id", read_only=True)
    collection_name = serializers.CharField(source="collection.name", read_only=True)

    class Meta:
        model = LandmarkCollectionUserPermission
        fields = [
            "id",
            "user",
            "user_email",
            "user_id",
            "user_full_name",
            "user_display_email",
            "collection",
            "collection_id",
            "collection_name",
            "level",
            "level_label",
            "creation_date",
            "modified_date",
        ]
        read_only_fields = [
            "id",
            "user",
            "collection",
            "creation_date",
            "modified_date",
        ]

    def get_user_full_name(self, obj: LandmarkCollectionUserPermission) -> str:
        if obj.user.first_name or obj.user.last_name:
            return f"{obj.user.first_name} {obj.user.last_name}".strip()
        return obj.user.email

    def validate_level(self, value: int) -> int:
        valid_levels = [
            PermissionLevel.READ_ONLY,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.ADMIN,
        ]
        if value not in valid_levels:
            raise serializers.ValidationError(
                f"Invalid permission level. Must be one of: {valid_levels}"
            )
        return value
