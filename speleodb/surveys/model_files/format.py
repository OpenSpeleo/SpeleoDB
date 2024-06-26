#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.db import models

from speleodb.surveys.models import Project
from speleodb.utils.decorators import classproperty


class NoUpdateQuerySet(models.QuerySet):
    def update(self, *args, **kwargs):
        pass


class Format(models.Model):
    project = models.ForeignKey(
        Project,
        related_name="rel_formats",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    class FileFormat(models.IntegerChoices):
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

        __excluded_download_formats__ = [OTHER, AUTO]
        __excluded_upload_formats__ = [OTHER, DUMP]
        __excluded_db_formats__ = [AUTO, DUMP]

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

        @classmethod
        def filtered_choices(cls, exclude_vals=None, as_str=True):
            exclude_vals = exclude_vals if not None else []

            filtered_list = [f for f in cls.choices if f not in exclude_vals]
            if as_str:
                return [f.lower() for _, f in filtered_list]
            return filtered_list

        @classproperty
        def download_choices(cls):  # noqa: N805
            return cls.filtered_choices(exclude_vals=cls.__excluded_download_formats__)

        @classproperty
        def upload_choices(cls):  # noqa: N805
            return cls.filtered_choices(exclude_vals=cls.__excluded_upload_formats__)

        @classproperty
        def db_choices(cls):  # noqa: N805
            return cls.filtered_choices(
                exclude_vals=cls.__excluded_db_formats__, as_str=False
            )

        @property
        def webname(self):
            return self.label.replace("_", " ")

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

    def __str__(self):
        return f"{self.project} -> {self.format}"

    def save(self, *args, **kwargs):
        # Only allows object creation. Otherwise bypass.
        if self.pk is None:
            super().save(*args, **kwargs)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    @property
    def raw_format(self) -> str:
        return self.FileFormat(self._format)

    @property
    def format(self) -> str:
        return self.raw_format.label

    @format.setter
    def format(self, value):
        self._format = value
