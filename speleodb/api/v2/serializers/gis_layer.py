# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import FileExtensionValidator
from django.db import transaction
from rest_framework import serializers

from speleodb.common.enums import ColorPalette
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISLayer
from speleodb.gis.models import GISLayerSourceFormat
from speleodb.gis.models import GISLayerUserPermission
from speleodb.gis.models.gis_layer import GIS_LAYER_SOURCE_EXTENSIONS
from speleodb.utils.sanitize import sanitize_text
from speleodb.utils.serializer_fields import CustomChoiceField
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from speleodb.gis.gis_layer_processing.types import CompilationResult

logger = logging.getLogger(__name__)


def safe_upload_filename(filename: str) -> str:
    basename = PurePosixPath(filename.replace("\\", "/")).name
    basename = "".join(character for character in basename if character.isprintable())
    sanitized = sanitize_text(basename).strip()
    return sanitized[:255] or "source"


def declared_source_format(filename: str) -> GISLayerSourceFormat | None:
    suffix = PurePosixPath(filename).suffix.lower()
    match suffix:
        case ".kml":
            return GISLayerSourceFormat.KML
        case ".kmz":
            return GISLayerSourceFormat.KMZ
        case ".json" | ".geojson":
            return GISLayerSourceFormat.GEOJSON
        case ".topojson":
            return GISLayerSourceFormat.TOPOJSON
        case ".zip":
            return GISLayerSourceFormat.SHAPEFILE
        case _:
            return None


class GISLayerSerializer(SanitizedFieldsMixin, serializers.ModelSerializer[GISLayer]):
    sanitized_fields: ClassVar[list[str]] = ["name", "description"]

    file = serializers.SerializerMethodField()
    source_format = serializers.CharField(read_only=True)
    user_permission_level = serializers.IntegerField(read_only=True, required=False)
    user_permission_level_label = serializers.SerializerMethodField()
    can_write = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    can_manage_permissions = serializers.SerializerMethodField()

    class Meta:
        model = GISLayer
        fields = [
            "id",
            "name",
            "description",
            "color",
            "created_by",
            "file",
            "source_format",
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
            "file",
            "source_format",
            "user_permission_level",
            "user_permission_level_label",
            "can_write",
            "can_delete",
            "can_manage_permissions",
            "creation_date",
            "modified_date",
        ]

    def _permission_level(self, obj: GISLayer) -> int | None:
        return getattr(obj, "user_permission_level", None)

    def get_file(self, obj: GISLayer) -> str:
        return obj.get_signed_download_url()

    def get_user_permission_level_label(self, obj: GISLayer) -> str | None:
        level = self._permission_level(obj)
        return None if level is None else str(PermissionLevel.from_value(level).label)

    def get_can_write(self, obj: GISLayer) -> bool:
        level = self._permission_level(obj)
        return level is not None and level >= PermissionLevel.READ_AND_WRITE

    def get_can_delete(self, obj: GISLayer) -> bool:
        level = self._permission_level(obj)
        return level is not None and level >= PermissionLevel.ADMIN

    def get_can_manage_permissions(self, obj: GISLayer) -> bool:
        return self.get_can_delete(obj)

    def validate_color(self, value: str) -> str:
        value = value.strip()
        if not ColorPalette.is_valid_hex(value):
            raise serializers.ValidationError(
                "Color must be a valid hex color (e.g. #e41a1c)"
            )
        return value.lower()


class GISLayerCreateSerializer(GISLayerSerializer):
    source_file = serializers.FileField(
        write_only=True,
        validators=[FileExtensionValidator(GIS_LAYER_SOURCE_EXTENSIONS)],
    )

    class Meta(GISLayerSerializer.Meta):
        fields = [*GISLayerSerializer.Meta.fields, "source_file"]

    declared_source_format = staticmethod(declared_source_format)

    def create(self, validated_data: dict[str, Any]) -> GISLayer:
        request = self.context["request"]
        compilation_result: CompilationResult | None = validated_data.pop(
            "compilation_result",
            None,
        )
        source_file: UploadedFile = validated_data.pop("source_file")
        original_filename = safe_upload_filename(source_file.name or "source")
        layer = GISLayer(created_by=request.user.email, **validated_data)
        written_files: list[tuple[Any, str]] = []

        try:
            layer.source_f.save(original_filename, source_file, save=False)
            if layer.source_f.name:
                written_files.append((layer.source_f.storage, layer.source_f.name))

            if compilation_result is None:
                layer.data_f.name = layer.source_f.name
            else:
                layer.data_f.save(
                    "data.geojson",
                    SimpleUploadedFile(
                        "data.geojson",
                        compilation_result.display_geojson,
                        content_type="application/geo+json",
                    ),
                    save=False,
                )
                if layer.data_f.name:
                    written_files.append((layer.data_f.storage, layer.data_f.name))

            with transaction.atomic():
                layer.save()
                GISLayerUserPermission.objects.create(
                    user=request.user,
                    gis_layer=layer,
                    level=PermissionLevel.ADMIN,
                )
        except Exception:
            for storage, name in reversed(written_files):
                try:
                    storage.delete(name)
                except Exception:
                    logger.exception("Failed to clean an unpublished GIS Layer file.")
            raise

        layer.user_permission_level = PermissionLevel.ADMIN  # type: ignore[attr-defined]
        return layer


class GISLayerUserPermissionSerializer(
    serializers.ModelSerializer[GISLayerUserPermission]
):
    user = serializers.SlugRelatedField(read_only=True, slug_field="email")  # type: ignore[var-annotated]
    level = CustomChoiceField(PermissionLevel.choices_no_webviewer)

    class Meta:
        model = GISLayerUserPermission
        fields = ("user", "level", "creation_date", "modified_date")
        read_only_fields = ("user", "creation_date", "modified_date")
