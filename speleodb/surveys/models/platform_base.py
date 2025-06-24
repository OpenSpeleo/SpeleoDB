# -*- coding: utf-8 -*-

from __future__ import annotations

from speleodb.utils.django_base_models import BaseIntegerChoices


class SurveyPlatformEnum(BaseIntegerChoices):
    WEB = (0, "WEB")
    ARIANE = (1, "ARIANE")


class OperatingSystemEnum(BaseIntegerChoices):
    ANY = (0, "ANY")

    MACOS = (10, "MACOS")
    MACOS_INTEL = (11, "MACOS_INTEL")
    MACOS_ARM = (12, "MACOS_ARM")

    WINDOWS = (20, "WINDOWS")
    WINDOWS_32 = (21, "WINDOWS_32")
    WINDOWS_64 = (22, "WINDOWS_64")

    LINUX = (30, "LINUX")
    LINUX_32 = (31, "LINUX_32")
    LINUX_64 = (32, "LINUX_64")
