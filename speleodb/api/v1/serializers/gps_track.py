# -*- coding: utf-8 -*-

from __future__ import annotations

from rest_framework import serializers

from speleodb.gis.models import GPSTrack


class GPSTrackSerializer(serializers.ModelSerializer[GPSTrack]):
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
