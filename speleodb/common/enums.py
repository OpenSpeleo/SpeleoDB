# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Self

from django.db import models

from speleodb.utils.decorators import classproperty

if TYPE_CHECKING:
    from typing import Self

    from django_stubs_ext import StrOrPromise


class BaseIntegerChoices(models.IntegerChoices):
    @classmethod
    def from_str(cls, value: str) -> Self:
        return cls._member_map_[value]  # type: ignore[return-value]

    @classmethod
    def from_value(cls, value: int) -> Self:
        return cls._value2member_map_[value]  # type: ignore[return-value]

    @classproperty
    def members(cls) -> list[Self]:  # noqa: N805
        return list(cls._member_map_.values())  # type: ignore[attr-defined]


class InstallStatus(models.TextChoices):
    INSTALLED = "installed", "Installed"
    RETRIEVED = "retrieved", "Retrieved"
    LOST = "lost", "Lost"
    ABANDONED = "abandoned", "Abandoned"


class OperationalStatus(models.TextChoices):
    FUNCTIONAL = "functional", "Functional"
    NEEDS_SERVICE = "needs_service", "Needs Service"
    BROKEN = "broken", "Broken"
    LOST = "lost", "Lost"
    ABANDONED = "abandoned", "Abandoned"


class PermissionLevel(BaseIntegerChoices):
    WEB_VIEWER = (0, "WEB_VIEWER")
    READ_ONLY = (1, "READ_ONLY")
    READ_AND_WRITE = (2, "READ_AND_WRITE")
    ADMIN = (3, "ADMIN")

    @classproperty
    def choices_no_admin(cls) -> list[tuple[int, StrOrPromise]]:  # noqa: N805
        return [
            member
            for member in PermissionLevel.choices
            if member[0] < PermissionLevel.ADMIN
        ]

    @classproperty
    def choices_no_webviewer(cls) -> list[tuple[int, StrOrPromise]]:  # noqa: N805
        return [
            member
            for member in PermissionLevel.choices
            if member[0] > PermissionLevel.WEB_VIEWER
        ]

    @classproperty
    def values_no_admin(cls) -> list[int]:  # noqa: N805
        return [
            value for value in PermissionLevel.values if value < PermissionLevel.ADMIN
        ]

    @classproperty
    def members_no_admin(cls) -> list[PermissionLevel]:  # noqa: N805
        return [  # type: ignore[var-annotated]
            member
            for member in PermissionLevel.members  # type: ignore[arg-type]
            if member.value < PermissionLevel.ADMIN.value
        ]

    @classproperty
    def members_no_webviewer(cls) -> list[PermissionLevel]:  # noqa: N805
        return [  # type: ignore[var-annotated]
            member
            for member in PermissionLevel.members  # type: ignore[arg-type]
            if member.value > PermissionLevel.WEB_VIEWER.value
        ]


class ProjectType(models.TextChoices):
    ARIANE = "ariane", "ARIANE"
    COMPASS = "compass", "COMPASS"
    STICKMAPS = "stickmaps", "STICKMAPS"
    THERION = "therion", "THERION"
    WALLS = "walls", "WALLS"
    OTHER = "other", "OTHER"


class ProjectVisibility(BaseIntegerChoices):
    PRIVATE = (0, "PRIVATE")
    PUBLIC = (1, "PUBLIC")


class StationResourceType(models.TextChoices):
    PHOTO = "photo", "Photo"
    VIDEO = "video", "Video"
    NOTE = "note", "Note"
    DOCUMENT = "document", "Document"

    @classmethod
    def from_str(cls, value: str) -> Self:
        return cls._member_map_[value.upper()]  # type: ignore[return-value]


class SubSurfaceStationType(models.TextChoices):
    ARTIFACT = "artifact", "Artifact"
    BIOLOGY = "biology", "Biology"
    BONE = "bone", "Bone"
    GEOLOGY = "geology", "Geology"
    SENSOR = "sensor", "Sensor"


class SurveyTeamMembershipRole(BaseIntegerChoices):
    MEMBER = (0, "MEMBER")
    LEADER = (1, "LEADER")


class UnitSystem(models.TextChoices):
    METRIC = "metric", "Metric"
    IMPERIAL = "imperial", "Imperial"


# =============================================================================
# SpeleoDB Platform Plugin Enums
# =============================================================================


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
