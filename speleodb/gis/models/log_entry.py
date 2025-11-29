# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from django.db import models

from speleodb.gis.models import Station
from speleodb.gis.models import SubSurfaceStation
from speleodb.gis.models import SurfaceStation
from speleodb.utils.storages import AttachmentStorage
from speleodb.utils.validators import AttachmentValidator

logger = logging.getLogger(__name__)


def get_log_entry_path(instance: StationLogEntry, filename: str) -> str:
    """
    Determine path prefix based on station type
    SubSurfaceStation has 'project', SurfaceStation has 'network'"""
    ext = Path(filename).suffix[1:]

    prefix: str

    # ForeignKey to polymorphic model returns base class by default
    # Call get_real_instance() to get the actual polymorphic child
    match station := instance.station.get_real_instance():  # type: ignore[no-untyped-call]
        case SubSurfaceStation():
            prefix = f"{station.project.id}"
        case SurfaceStation():
            prefix = f"{station.network.id}"
        case _:
            raise ValueError(
                "Unsupported station type for log entry path generation: "
                f"{type(station)}"
            )

    return f"{prefix}/{instance.station.id}/logs/{os.urandom(6).hex()}.{ext}"


class StationLogEntry(models.Model):
    """A scientific log or observation recorded at a specific Station."""

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="log_entries",
        help_text="The station or location this log entry is associated with.",
    )

    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created or submitted the entry.",
    )

    title = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        help_text="Short title or summary of the observation.",
    )

    notes = models.TextField(
        blank=True,
        help_text="Detailed field notes, observations, or measurements.",
    )

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    attachment = models.FileField(
        upload_to=get_log_entry_path,
        blank=True,
        null=True,
        storage=AttachmentStorage(),  # type: ignore[no-untyped-call]
        validators=[AttachmentValidator()],
        help_text="Any relevant file (sketch, lab sheet, sensor data, etc.).",
    )

    class Meta:
        ordering = ["-creation_date"]
        verbose_name_plural = "Log Entries"
        indexes = [
            models.Index(fields=["station"]),
        ]

    def __str__(self) -> str:
        return (
            f"[Station: `{self.station.name}`] "
            f'{self.creation_date.strftime("%Y-%m-%d %H:%M")} => "{self.title}"'
        )
