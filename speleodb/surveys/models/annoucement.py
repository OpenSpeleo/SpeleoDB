# -*- coding: utf-8 -*-

from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models
from packaging.version import Version

from speleodb.utils.django_base_models import BaseIntegerChoices


class PlatformEnum(BaseIntegerChoices):
    WEB = (0, "WEB")
    ARIANE = (1, "ARIANE")


# https://semver.org/#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string
SEMVER_REGEX = r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$"
CALVER_REGEX = r"^(?P<year>2[0-9]{3}).(?P<month>1[0-2]|0?[1-9]).(?P<day>3[0-1]|[1-2][0-9]|0?[1-9])$"  # noqa: E501

version_validator = RegexValidator(
    regex=f"({SEMVER_REGEX})|({CALVER_REGEX})",
    message="Enter a valid SemVer (e.g., 1.2.3) or CalVer (e.g., 2025.06)",
)


class PublicAnnoucement(models.Model):
    title = models.CharField(max_length=255)
    header = models.CharField(max_length=255)
    message = models.TextField()

    software = models.IntegerField(
        choices=PlatformEnum.choices,
        null=False,
        blank=False,
    )

    _version = models.CharField(
        default="",
        blank=True,
        max_length=50,
        validators=[version_validator],
    )

    is_active = models.BooleanField(default=True)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)
    expiracy_date = models.DateField(default=None, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.title}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    @property
    def version(self) -> Version | None:
        if self._version:
            return Version(self._version)
        return None

    @version.setter
    def version(self, value: str | Version | None) -> None:
        if isinstance(value, str):
            self._version = str(Version(value))
        elif isinstance(value, Version):
            self._version = str(value)
        elif value is None:
            self._version = ""
        else:
            raise ValueError(f"Unknown value received: {value}")
