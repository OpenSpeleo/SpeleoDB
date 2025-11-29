# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from polymorphic.models import PolymorphicModel

from speleodb.gis.models import StationTag
from speleodb.gis.models import SurfaceMonitoringNetwork

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from speleodb.gis.models import ExperimentRecord
    from speleodb.gis.models import StationLogEntry
    from speleodb.gis.models import StationResource


class Station(PolymorphicModel):
    """
    Represents a survey station where field data collection occurs.
    Stations are positioned using latitude/longitude coordinates.
    """

    # type checking
    resources: models.QuerySet[StationResource]
    log_entries: models.QuerySet[StationLogEntry]
    rel_records: models.QuerySet[ExperimentRecord]

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    # Station identification
    name = models.CharField(
        max_length=100, help_text="Station identifier (e.g., 'A1', 'Station-001')"
    )

    description = models.TextField(
        blank=True, default="", help_text="Optional description of the station"
    )

    # Station coordinates
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=False,
        blank=False,
        help_text="Station latitude coordinate",
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=False,
        blank=False,
        help_text="Station longitude coordinate",
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    tag = models.ForeignKey(
        StationTag,
        related_name="stations",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    # Metadata
    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created or submitted the entry.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-modified_date"]
        indexes = [
            models.Index(fields=["tag"]),
            models.Index(fields=["latitude", "longitude"]),  # for spatial queries
        ]

    def __str__(self) -> str:
        return f"Station {self.name}"

    @property
    def coordinates(self) -> tuple[float, float] | None:
        """Get current coordinates as (longitude, latitude) tuple."""
        if self.latitude is not None and self.longitude is not None:
            return (float(self.longitude), float(self.latitude))
        return None


class SubSurfaceStation(Station):
    """
    Represents a subsurface survey station.
    Inherits from Station.
    """

    # Project relationship
    project = models.ForeignKey(
        "surveys.Project",
        related_name="rel_stations",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    class Meta:
        verbose_name = "Station - Subsurface"
        verbose_name_plural = "Stations - Subsurface"
        indexes = [
            models.Index(fields=["project"]),
        ]


class SurfaceStation(Station):
    """
    Represents a surface survey station.
    Inherits from Station.
    """

    network = models.ForeignKey(
        SurfaceMonitoringNetwork,
        related_name="rel_stations",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    class Meta:
        verbose_name = "Station - Surface"
        verbose_name_plural = "Stations - Surface"
        indexes = [
            models.Index(fields=["network"]),
        ]
