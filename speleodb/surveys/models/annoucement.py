# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid

from django.db import models

from speleodb.surveys.fields import VersionField
from speleodb.surveys.models.platform_base import SurveyPlatformEnum


class PublicAnnoucement(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        blank=False,
        null=False,
        unique=True,
        verbose_name="UUID",
    )

    title = models.CharField(max_length=255)
    header = models.CharField(max_length=255)
    message = models.TextField()

    software = models.IntegerField(
        choices=SurveyPlatformEnum.choices,
        null=False,
        blank=False,
    )

    version = VersionField(
        default="",
        blank=True,
        # verbose_name="Version",
    )

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)
    expiracy_date = models.DateField(default=None, null=True, blank=True)

    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
    )

    def __str__(self) -> str:
        return f"{self.title}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"
