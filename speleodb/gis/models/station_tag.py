# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.core.validators import RegexValidator
from django.db import models

if TYPE_CHECKING:
    from speleodb.gis.models import Station


class StationTag(models.Model):
    """
    Represents a tag that can be assigned to stations.
    Similar to GitHub's label system for issues/PRs.
    Each tag has a name, color, and is owned by a user.
    """

    stations: models.QuerySet[Station]

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    name = models.CharField(
        max_length=50,
        help_text="Tag name (e.g., 'Active', 'High Priority', 'Completed')",
    )

    color = models.CharField(
        max_length=7,
        help_text="Hex color code (e.g., '#FF5733')",
        validators=[
            RegexValidator(
                regex=r"^#[0-9A-Fa-f]{6}$",
                message="Color must be a valid hex code (e.g., '#FF5733')",
            )
        ],
    )

    user = models.ForeignKey(
        "users.User",
        related_name="station_tags",
        on_delete=models.CASCADE,
        help_text="User who created the tag",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Station Tag"
        verbose_name_plural = "Station Tags"
        ordering = ["user", "name"]
        indexes = [
            models.Index(fields=["user"]),
            # models.Index(fields=["user", "name"]),  # present via unique_together
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="%(app_label)s_%(class)s_user_tag_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.color})"

    @staticmethod
    def get_predefined_colors() -> list[str]:
        """
        Return a list of 20 well-spaced colors for tag selection.
        These colors are chosen to be visually distinct and work well on maps.
        """
        return [
            "#ef4444",  # Red
            "#f97316",  # Orange
            "#f59e0b",  # Amber
            "#eab308",  # Yellow
            "#84cc16",  # Lime
            "#22c55e",  # Green
            "#10b981",  # Emerald
            "#14b8a6",  # Teal
            "#06b6d4",  # Cyan
            "#0ea5e9",  # Sky
            "#3b82f6",  # Blue
            "#6366f1",  # Indigo
            "#8b5cf6",  # Violet
            "#a855f7",  # Purple
            "#d946ef",  # Fuchsia
            "#ec4899",  # Pink
            "#f43f5e",  # Rose
            "#fb7185",  # Light Rose
            "#fb923c",  # Vibrant Orange
            "#facc15",  # Bright Yellow
        ]
