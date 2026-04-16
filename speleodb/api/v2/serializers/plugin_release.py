# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework import serializers

from speleodb.common.enums import OperatingSystemEnum
from speleodb.common.enums import SurveyPlatformEnum
from speleodb.plugins.models import PluginRelease

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise
else:
    StrOrPromise = str  # necessary for swagger


class PluginReleaseSerializer(serializers.ModelSerializer[PluginRelease]):
    min_software_version = serializers.SerializerMethodField()
    max_software_version = serializers.SerializerMethodField()
    software = serializers.SerializerMethodField()
    operating_system = serializers.SerializerMethodField()

    class Meta:
        fields = "__all__"
        model = PluginRelease

    def get_min_software_version(self, obj: PluginRelease) -> str | None:
        return obj.min_software_version or None

    def get_max_software_version(self, obj: PluginRelease) -> str | None:
        return obj.max_software_version or None

    def get_software(self, obj: PluginRelease) -> StrOrPromise:
        return SurveyPlatformEnum(obj.software).label

    def get_operating_system(self, obj: PluginRelease) -> StrOrPromise:
        return OperatingSystemEnum(obj.operating_system).label
