# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import ClassVar

from rest_framework import serializers

from speleodb.plugins.models import PublicAnnoucement
from speleodb.plugins.models.platform_base import SurveyPlatformEnum
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise
else:
    StrOrPromise = str  # necessary for swagger


class PublicAnnoucementSerializer(
    SanitizedFieldsMixin, serializers.ModelSerializer[PublicAnnoucement]
):
    sanitized_fields: ClassVar[list[str]] = ["title", "header", "message"]
    version = serializers.SerializerMethodField()
    software = serializers.SerializerMethodField()

    class Meta:
        fields = "__all__"
        model = PublicAnnoucement

    def get_version(self, obj: PublicAnnoucement) -> str | None:
        return obj.version or None

    def get_software(self, obj: PublicAnnoucement) -> StrOrPromise:
        return SurveyPlatformEnum(obj.software).label
