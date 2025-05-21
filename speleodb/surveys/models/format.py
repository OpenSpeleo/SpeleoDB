#!/usr/bin/env python
# -*- coding: utf-8 -*-
from typing import Any

from django.db import models

from speleodb.surveys.models import Project
from speleodb.utils.decorators import classproperty
from speleodb.utils.django_base_models import BaseIntegerChoices


class NoUpdateQuerySet(models.QuerySet["Format"]):
    def update(self, **kwargs: Any) -> int:
        return 0


class Format(models.Model):
    project = models.ForeignKey(
        Project,
        related_name="rel_formats",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    class FileFormat(BaseIntegerChoices):
        # NOTE: Special values that don't really represent a "file format":
        # ------------------------------------------------------------------------------

        # - `OTHER`: is a wildchar format. Anything that doesn't fit the other format
        #   will just be saved as a file without any special treatment.
        OTHER = (1000, "OTHER")

        # - `AUTO`: not a format. Upload endpoint that automatically detects the format.
        AUTO = (9998, "AUTO")

        # - `DUMP`: not a format. Download endpoint that packages and returns everything
        #   as a zipfile.
        DUMP = (9999, "DUMP")

        # NOTE: Recognized Software Formats that will undergo a special process.
        # ------------------------------------------------------------------------------
        # Each software gets a new 10s.
        # It allows to insert new formats without having to shift everyone.
        # Hopefully no software uses more than 10 different file formats.

        # Ariane Line
        ARIANE_TML = (10, "ARIANE_TML")
        ARIANE_TMLU = (11, "ARIANE_TMLU")
        ARIANE_AGR = (12, "ARIANE_AGR")

        # Compass
        COMPASS_MAK = (20, "COMPASS_MAK")
        COMPASS_DAT = (21, "COMPASS_DAT")

        # Walls
        WALLS_SRV = (30, "WALLS_SRV")
        WALLS_WPJ = (31, "WALLS_WPJ")

        # StickMaps
        STICKMAPS = (40, "STICKMAPS")

        @property
        def webname(self) -> str:
            return self.label.replace("_", " ")

        @classmethod
        def filtered_choices(
            cls, exclude_vals: list[tuple[int, str]] | None = None
        ) -> list[tuple[int, str]]:
            exclude_vals = exclude_vals if exclude_vals is not None else []

            return [f for f in cls.choices if f not in exclude_vals]

        @classmethod
        def filtered_choices_as_str(
            cls, exclude_vals: list[tuple[int, str]] | None = None
        ) -> list[str]:
            return [
                f.lower() for _, f in cls.filtered_choices(exclude_vals=exclude_vals)
            ]

        @classproperty
        def download_choices(cls) -> list[str]:  # noqa: N805
            return cls.filtered_choices_as_str(
                exclude_vals=cls.__excluded_download_formats__
            )

        @classproperty
        def upload_choices(cls) -> list[str]:  # noqa: N805
            return cls.filtered_choices_as_str(
                exclude_vals=cls.__excluded_upload_formats__
            )

        @classproperty
        def db_choices(cls) -> list[tuple[int, str]]:  # noqa: N805
            return cls.filtered_choices(exclude_vals=cls.__excluded_db_formats__)

        @classproperty
        def __excluded_download_formats__(cls) -> list[tuple[int, str]]:  # noqa: N805
            return [cls.OTHER, cls.AUTO]

        @classproperty
        def __excluded_upload_formats__(cls) -> list[tuple[int, str]]:  # noqa: N805
            return [cls.DUMP]

        @classproperty
        def __excluded_db_formats__(cls) -> list[tuple[int, str]]:  # noqa: N805
            return [cls.DUMP, cls.AUTO]

    _format = models.IntegerField(
        choices=FileFormat.db_choices,
        verbose_name="format",
        blank=False,
        null=False,
    )

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)

    # Object Manager disabling update
    objects = NoUpdateQuerySet.as_manager()

    class Meta:
        unique_together = (
            "project",
            "_format",
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.project} -> {self.format}"

    def save(self, *args: list[Any], **kwargs: dict[str, Any]) -> None:
        # Only allows object creation. Otherwise bypass.
        if self.pk is None:
            super().save(*args, **kwargs)

    @property
    def raw_format(self) -> str:
        return self.FileFormat(self._format)

    @property
    def format(self) -> str:
        return self.raw_format.label

    @format.setter
    def format(self, value) -> None:
        self._format = value
