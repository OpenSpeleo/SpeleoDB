# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework import serializers

from speleodb.surveys.models import PluginRelease
from speleodb.surveys.models.platform_base import OperatingSystemEnum
from speleodb.surveys.models.platform_base import SurveyPlatformEnum

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise
else:
    StrOrPromise = str  # necessary for swagger


class PluginReleaseSerializer(serializers.ModelSerializer[PluginRelease]):
    software_version = serializers.SerializerMethodField()
    software = serializers.SerializerMethodField()
    operating_system = serializers.SerializerMethodField()

    class Meta:
        fields = "__all__"
        model = PluginRelease

    def get_software_version(self, obj: PluginRelease) -> str | None:
        return obj.software_version or None

    def get_software(self, obj: PluginRelease) -> StrOrPromise:
        return SurveyPlatformEnum(obj.software).label

    def get_operating_system(self, obj: PluginRelease) -> StrOrPromise:
        return OperatingSystemEnum(obj.operating_system).label
