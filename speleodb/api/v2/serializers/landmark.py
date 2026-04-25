# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from decimal import InvalidOperation
from typing import Any
from typing import ClassVar

from geojson import Feature  # type: ignore[attr-defined]
from geojson import Point  # type: ignore[attr-defined]
from rest_framework import serializers

from speleodb.api.v2.landmark_access import user_has_collection_access
from speleodb.api.v2.landmark_access import user_has_landmark_access
from speleodb.common.enums import PermissionLevel
from speleodb.gis.landmark_collections import get_or_create_personal_landmark_collection
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
from speleodb.utils.gps_utils import format_coordinate
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin


class LandmarkSerializer(SanitizedFieldsMixin, serializers.ModelSerializer[Landmark]):
    """Serializer for Landmark with all details."""

    sanitized_fields: ClassVar[list[str]] = ["name", "description"]

    collection = serializers.PrimaryKeyRelatedField(
        queryset=LandmarkCollection.objects.filter(is_active=True),
        allow_null=True,
        required=False,
    )
    collection_name = serializers.CharField(
        source="collection.name",
        read_only=True,
        allow_null=True,
    )
    collection_color = serializers.CharField(
        source="collection.color",
        read_only=True,
        allow_null=True,
    )
    can_write = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Landmark
        fields = "__all__"
        validators: ClassVar[list[Any]] = []
        read_only_fields = [
            "id",
            "creation_date",
            "modified_date",
            "created_by",
            "collection_name",
            "collection_color",
            "can_write",
            "can_delete",
        ]

    def _get_request_user(self) -> Any:
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            return request.user
        return None

    def get_can_write(self, obj: Landmark) -> bool:
        user = self._get_request_user()
        if user is None:
            return False
        return user_has_landmark_access(
            user=user,
            landmark=obj,
            min_level=PermissionLevel.READ_AND_WRITE,
        )

    def get_can_delete(self, obj: Landmark) -> bool:
        return self.get_can_write(obj)

    def validate_collection(
        self, collection: LandmarkCollection | None
    ) -> LandmarkCollection | None:
        if collection is None:
            return collection

        user = self._get_request_user()
        if user is None:
            raise serializers.ValidationError(
                "Authentication is required to assign a collection."
            )

        if not user_has_collection_access(
            user=user,
            collection=collection,
            min_level=PermissionLevel.READ_AND_WRITE,
        ):
            raise serializers.ValidationError(
                "WRITE access is required to assign landmarks to this collection."
            )

        return collection

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        user = self._get_request_user()
        if user is not None and self.instance is None:
            if attrs.get("collection") is None:
                attrs["collection"] = get_or_create_personal_landmark_collection(
                    user=user,
                )
            return attrs

        if self.instance is None:
            return attrs

        if user is None:
            return attrs

        if attrs.get("collection") is None and "collection" in attrs:
            attrs["collection"] = get_or_create_personal_landmark_collection(
                user=user,
            )

        if not user_has_landmark_access(
            user=user,
            landmark=self.instance,
            min_level=PermissionLevel.READ_AND_WRITE,
        ):
            raise serializers.ValidationError(
                "WRITE access is required to update this collection landmark."
            )

        return attrs

    def create(self, validated_data: Any) -> Landmark:
        """Create a new Landmark and set creator metadata from request user."""
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            validated_data["created_by"] = request.user.email
            if validated_data.get("collection") is None:
                validated_data["collection"] = (
                    get_or_create_personal_landmark_collection(
                        user=request.user,
                    )
                )

        return super().create(validated_data)

    def to_internal_value(self, data: dict[str, Any]) -> Any:
        """Override to round coordinates before validation."""

        # Data is immutable - need to copy
        data = data.copy()

        # Round coordinates if they exist in the data
        if "latitude" in data and data["latitude"] is not None:
            with contextlib.suppress(ValueError, TypeError, InvalidOperation):
                # Let the field validation handle the error
                data["latitude"] = format_coordinate(data["latitude"])

        if "longitude" in data and data["longitude"] is not None:
            with contextlib.suppress(ValueError, TypeError, InvalidOperation):
                # Let the field validation handle the error
                data["longitude"] = format_coordinate(data["longitude"])

        return super().to_internal_value(data)

    def to_representation(self, instance: Landmark) -> dict[str, Any]:
        """Ensure coordinates are rounded to 7 decimal places."""
        data = super().to_representation(instance)
        if data.get("latitude") is not None:
            data["latitude"] = format_coordinate(data["latitude"])
        if data.get("longitude") is not None:
            data["longitude"] = format_coordinate(data["longitude"])
        return data


class LandmarkGeoJSONSerializer(serializers.ModelSerializer[Landmark]):
    """Map serializer for Landmarks - returns GeoJSON-like format."""

    class Meta:
        model = Landmark
        fields = [
            "id",
            "name",
            "description",
            "latitude",
            "longitude",
            "collection",
            "created_by",
            "creation_date",
        ]

    def _get_request_user(self) -> Any:
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            return request.user
        return None

    def to_representation(self, instance: Landmark) -> dict[str, Any]:
        """Convert to GeoJSON Feature format."""
        user = self._get_request_user()
        can_write = (
            user_has_landmark_access(
                user=user,
                landmark=instance,
                min_level=PermissionLevel.READ_AND_WRITE,
            )
            if user is not None
            else False
        )

        return Feature(  # type: ignore[no-untyped-call]
            id=str(instance.id),
            geometry=Point((float(instance.longitude), float(instance.latitude))),  # type: ignore[no-untyped-call]
            properties={
                "name": instance.name,
                "description": instance.description,
                "collection": str(instance.collection_id),
                "collection_name": instance.collection.name,
                "collection_type": instance.collection.collection_type,
                "collection_color": instance.collection.color,
                "is_personal_collection": instance.collection.is_personal,
                "can_write": can_write,
                "can_delete": can_write,
                "created_by": instance.created_by,
                "creation_date": instance.creation_date.isoformat()
                if instance.creation_date
                else None,
            },
        )
