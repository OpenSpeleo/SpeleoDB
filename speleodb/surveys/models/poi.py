# -*- coding: utf-8 -*-

from __future__ import annotations

import decimal
import uuid

from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models


class PointOfInterest(models.Model):
    """
    Represents a Point of Interest (POI) on the map.
    POIs are standalone markers not linked to any project.
    """

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
        unique=True,
    )

    # POI identification
    name = models.CharField(
        max_length=100,
        help_text="Point of Interest name (must be unique)",
    )

    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of the point of interest",
    )

    # POI coordinates
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        help_text="POI latitude coordinate",
        validators=[
            MinValueValidator(decimal.Decimal("-90.0")),
            MaxValueValidator(decimal.Decimal("90.0")),
        ],
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        help_text="POI longitude coordinate",
        validators=[
            MinValueValidator(decimal.Decimal("-180.0")),
            MaxValueValidator(decimal.Decimal("180.0")),
        ],
    )

    # Metadata
    created_by = models.ForeignKey(
        "users.User", related_name="pois_created", on_delete=models.CASCADE
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Point of Interest"
        verbose_name_plural = "Points of Interest"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["latitude", "longitude"]),  # For spatial queries
            models.Index(fields=["name"]),  # For name lookups
            models.Index(fields=["creation_date"]),  # For recent POIs
        ]

    def __str__(self) -> str:
        return f"POI: {self.name}"

    @property
    def coordinates(self) -> tuple[float, float] | None:
        """Get current coordinates as (longitude, latitude) tuple."""
        if self.latitude is not None and self.longitude is not None:
            return (float(self.longitude), float(self.latitude))
        return None
