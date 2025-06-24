# -*- coding: utf-8 -*-

from __future__ import annotations

from django.db import models

from speleodb.surveys.fields import Sha256Field
from speleodb.surveys.fields import VersionField
from speleodb.surveys.models.platform_base import OperatingSystemEnum
from speleodb.surveys.models.platform_base import SurveyPlatformEnum


class PluginRelease(models.Model):
    plugin_version = VersionField(
        verbose_name="Plugin version",
    )

    software = models.IntegerField(
        choices=SurveyPlatformEnum.choices,
        null=False,
        blank=False,
    )

    software_version = VersionField(
        default="",
        blank=True,
        verbose_name="Software version",
    )

    operating_system = models.IntegerField(
        choices=OperatingSystemEnum.choices,
        default=OperatingSystemEnum.ANY,
        null=False,
        blank=False,
    )

    changelog = models.TextField()

    sha256_hash = Sha256Field(
        unique=True,
        blank=True,
        null=True,
        verbose_name="SHA256 Hash",
    )

    download_url = models.URLField(max_length=500)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self) -> str:
        return (
            f"[{SurveyPlatformEnum(self.software).label} - {self.software_version}] "
            f"{self.plugin_version}: {self.download_url}"
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"
