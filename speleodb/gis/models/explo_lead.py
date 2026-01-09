# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import uuid

from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models

from speleodb.surveys.models import Project

logger = logging.getLogger(__name__)


class ExplorationLead(models.Model):
    """
    Represents an exploration lead for a given survey.
    """

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of the lead",
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

    project = models.ForeignKey(
        Project,
        related_name="exploration_leads",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
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
        verbose_name = "Exploration Lead"
        verbose_name_plural = "Exploration Leads"
        ordering = ["-modified_date"]
        indexes = [
            models.Index(fields=["latitude", "longitude"]),  # for spatial queries
            models.Index(fields=["project"]),
        ]

    def __str__(self) -> str:
        return f"[Project: `{self.project.name}`] Exploration Lead: {self.id}"

    @property
    def coordinates(self) -> tuple[float, float] | None:
        """Get current coordinates as (longitude, latitude) tuple."""
        if self.latitude is not None and self.longitude is not None:
            return (float(self.longitude), float(self.latitude))
        return None
