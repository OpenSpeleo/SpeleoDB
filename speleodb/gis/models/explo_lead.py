# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import math
import uuid

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.lookups import IsNull
from django.db.models.lookups import LessThanOrEqual

from speleodb.common.constants import EXPLORATION_LEAD_MAX_HEADINGS
from speleodb.common.constants import HEADING_FULL_CIRCLE
from speleodb.surveys.models import Project

logger = logging.getLogger(__name__)


def validate_headings(values: list[float]) -> None:
    """An unset direction list is empty; every supplied direction is renderable."""
    if len(values) > EXPLORATION_LEAD_MAX_HEADINGS or any(
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or not 0 <= value < HEADING_FULL_CIRCLE
        for value in values
    ):
        raise ValidationError(
            "Supply up to three headings from 0 inclusive to 360 exclusive."
        )


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

    headings = ArrayField(
        models.FloatField(),
        default=list,
        db_default=[],
        blank=True,
        size=EXPLORATION_LEAD_MAX_HEADINGS,
        validators=[validate_headings],
        help_text=(
            "Up to three directions clockwise from geographic north; empty is unset."
        ),
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
        constraints = [
            models.CheckConstraint(
                name="exploration_lead_valid_headings",
                condition=(
                    models.Q(headings__len__lte=3)
                    & LessThanOrEqual(
                        models.Func(
                            "headings",
                            function="array_ndims",
                            output_field=models.IntegerField(),
                        ),
                        models.Value(1),
                    )
                    & IsNull(
                        models.Func(
                            "headings",
                            models.Value(None, output_field=models.FloatField()),
                            function="array_position",
                            output_field=models.IntegerField(),
                        ),
                        rhs=True,
                    )
                    & (
                        models.Q(headings__len=0)
                        | models.Q(headings__0__gte=0, headings__0__lt=360)
                    )
                    & (
                        models.Q(headings__len__lte=1)
                        | models.Q(headings__1__gte=0, headings__1__lt=360)
                    )
                    & (
                        models.Q(headings__len__lte=2)
                        | models.Q(headings__2__gte=0, headings__2__lt=360)
                    )
                ),
            ),
        ]
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


class ExplorationLeadSource(models.Model):
    """A project-scoped signature retained after its imported lead is deleted."""

    class Kind(models.IntegerChoices):
        UUID = 1, "Native UUID"
        ENDPOINTS = 2, "Shot and origin IDs"
        MEASUREMENT = 3, "Shot ID and measurements"

    project = models.ForeignKey(
        Project,
        related_name="exploration_lead_sources",
        on_delete=models.CASCADE,
    )
    lead = models.ForeignKey(
        ExplorationLead,
        related_name="sources",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    kind = models.PositiveSmallIntegerField(choices=Kind.choices)
    digest = models.CharField(max_length=64)
    payload = models.JSONField()
    source_format = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "kind", "digest"],
                name="unique_project_lead_signature",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.project_id}: {self.get_kind_display()} {self.digest}"

    def clean(self) -> None:
        super().clean()
        if self.lead is not None and self.lead.project_id != self.project_id:
            raise ValidationError("A lead source must belong to the lead's project.")
