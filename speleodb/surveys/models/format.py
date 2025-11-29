# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import indexes
from django.utils import timezone

from speleodb.surveys.models import Project
from speleodb.utils.decorators import classproperty
from speleodb.utils.django_base_models import BaseIntegerChoices

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise

    type ListFileFormats = list[tuple[int, str] | FileFormat]


class NoUpdateQuerySet(models.QuerySet["Format"]):
    def update(self, **kwargs: Any) -> int:
        return 0


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
    COMPASS_ZIP = (20, "COMPASS_ZIP")
    COMPASS_MANUAL = (21, "COMPASS_MANUAL")

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
        cls, exclude_vals: ListFileFormats | None = None
    ) -> list[tuple[int, StrOrPromise]]:
        exclude_vals = exclude_vals if exclude_vals is not None else []

        return [f for f in cls.choices if f not in exclude_vals]

    @classmethod
    def filtered_choices_as_str(
        cls, exclude_vals: ListFileFormats | None = None
    ) -> list[str]:
        return [f.lower() for _, f in cls.filtered_choices(exclude_vals=exclude_vals)]

    @classproperty
    def download_choices(cls) -> list[str]:  # noqa: N805
        return cls.filtered_choices_as_str(
            exclude_vals=cls.__excluded_download_formats__
        )

    @classproperty
    def upload_choices(cls) -> list[str]:  # noqa: N805
        return cls.filtered_choices_as_str(exclude_vals=cls.__excluded_upload_formats__)

    @classproperty
    def db_choices(cls) -> list[tuple[int, StrOrPromise]]:  # noqa: N805
        return cls.filtered_choices(exclude_vals=cls.__excluded_db_formats__)

    @classproperty
    def __excluded_download_formats__(cls) -> ListFileFormats:  # noqa: N805
        return [cls.OTHER, cls.AUTO, cls.COMPASS_MANUAL]

    @classproperty
    def __excluded_upload_formats__(cls) -> ListFileFormats:  # noqa: N805
        return [cls.DUMP]

    @classproperty
    def __excluded_db_formats__(cls) -> ListFileFormats:  # noqa: N805
        return [cls.DUMP, cls.AUTO]


class Format(models.Model):
    project = models.ForeignKey(
        Project,
        related_name="rel_formats",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    # Note: `_format` because `format` is a reserved word in Python
    _format = models.IntegerField(
        choices=FileFormat.db_choices,
        verbose_name="format",
        blank=False,
        null=False,
    )

    creation_date = models.DateTimeField()

    # Object Manager disabling update
    objects: models.Manager[Format] = NoUpdateQuerySet.as_manager()

    class Meta:
        unique_together = (
            "project",
            "_format",
        )
        indexes = [
            indexes.Index(fields=["project"]),
            # indexes.Index(fields=["project", "_format"]), # Present via unique constraint  # noqa: E501
        ]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.project} -> {self.format}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        # `_from_admin=True` will only be passed by the admin form
        if self.pk is not None:
            if not kwargs.pop("_from_admin", False):
                before_obj = Format.objects.only("creation_date").get(pk=self.pk)
                if before_obj.creation_date != self.creation_date:
                    raise ValidationError("Creation date cannot be changed.")

            if self.creation_date > timezone.now():
                raise ValidationError("Creation date cannot be in the future.")

        # If saving outside admin and the instance is new, force creation_date to now
        else:
            self.creation_date = timezone.now()

        super().save(*args, **kwargs)

    @property
    def raw_format(self) -> FileFormat:
        return FileFormat(self._format)

    @property
    def format(self) -> StrOrPromise:
        return self.raw_format.label

    @format.setter
    def format(self, fmt: FileFormat) -> None:
        self._format = fmt.value
