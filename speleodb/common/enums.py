# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models

from speleodb.utils.decorators import classproperty
from speleodb.utils.django_base_models import BaseIntegerChoices

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise


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


class InstallStatus(models.TextChoices):
    INSTALLED = "installed", "Installed"
    RETRIEVED = "retrieved", "Retrieved"
    LOST = "lost", "Lost"
    ABANDONED = "abandoned", "Abandoned"


class OperationalStatus(models.TextChoices):
    FUNCTIONAL = "functional", "Functional"
    BROKEN = "broken", "Broken"
    LOST = "lost", "Lost"
    ABANDONED = "abandoned", "Abandoned"


class UnitSystem(models.TextChoices):
    METRIC = "metric", "Metric"
    IMPERIAL = "imperial", "Imperial"
