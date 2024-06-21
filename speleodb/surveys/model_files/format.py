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
        ARIANE = (0, "ARIANE")
        COMPASS = (1, "COMPASS")
        WALLS = (2, "WALLS")
        STICKMAPS = (3, "STICKMAPS")
        ZIP = (97, "ZIP")
        WEB = (98, "WEB")
        OTHER = (99, "OTHER")

        @classmethod
        def filtered_choices(cls, exclude_vals=None):
            exclude_vals = exclude_vals if not None else []
            return [f.lower() for _, f in cls.choices if f not in exclude_vals]

        @classproperty
        def download_choices(cls):  # noqa: N805
            return cls.filtered_choices(exclude_vals=["OTHER", "WEB"])

        @classproperty
        def upload_choices(cls):  # noqa: N805
            return cls.filtered_choices(exclude_vals=["OTHER", "ZIP"])

        @classproperty
        def db_choices(cls):  # noqa: N805
            exclude_vals = ["WEB", "ZIP"]
            return [(i, f) for i, f in cls.choices if f not in exclude_vals]

    _format = models.IntegerField(
        choices=FileFormat.db_choices,
        verbose_name="format",
        blank=False,
        null=False,
    )

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)

    objects = NoUpdateQuerySet.as_manager()

    class Meta:
        unique_together = (
            "project",
            "_format",
        )

    def __str__(self):
        return f"{self.project} -> {self.format}"

    def save(self, *args, **kwargs):
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
