# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework import serializers

from speleodb.surveys.models import PublicAnnoucement
from speleodb.surveys.models.annoucement import PlatformEnum

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise
else:
    StrOrPromise = str  # necessary for swagger


class PublicAnnoucementSerializer(serializers.ModelSerializer[PublicAnnoucement]):
    version = serializers.SerializerMethodField()
    software = serializers.SerializerMethodField()

    class Meta:
        exclude = ("_version",)
        model = PublicAnnoucement

    def get_version(self, obj: PublicAnnoucement) -> str | None:
        return obj._version or None  # noqa: SLF001

    def get_software(self, obj: PublicAnnoucement) -> StrOrPromise:
        return PlatformEnum(obj.software).label
