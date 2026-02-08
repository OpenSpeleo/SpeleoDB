# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from speleodb.gis.models import GPSTrack
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin


class GPSTrackSerializer(SanitizedFieldsMixin, serializers.ModelSerializer[GPSTrack]):
    sanitized_fields: ClassVar[list[str]] = ["name"]

    class Meta:
        model = GPSTrack
        fields = ["id", "name", "creation_date", "modified_date"]


class GPSTrackWithFileSerializer(serializers.ModelSerializer[GPSTrack]):
    file = serializers.SerializerMethodField()

    class Meta:
        model = GPSTrack
        fields = ["id", "name", "file", "sha256_hash", "creation_date", "modified_date"]
        read_only_fields = fields

    def get_file(self, obj: GPSTrack) -> str:
        """
        Retrieve the signed URL for the GeoJSON file
        """
        return obj.get_signed_download_url()
