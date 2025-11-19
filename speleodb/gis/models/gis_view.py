# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING
from typing import Any
from venv import logger

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Prefetch
from django.db.models import Q

from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.models.utils import generate_random_token
from speleodb.surveys.models import Project
from speleodb.users.models import User

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.models.base import ModelBase

sha1_regex = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


class GISView(models.Model):
    """
    A GIS View represents a curated collection of project GeoJSON data.

    Each view has a unique token that allows unauthenticated access to
    the specified projects and commits via a public API endpoint.

    Management: Django Admin or optional API endpoints
    Access: Public read-only API at /api/v1/gis/view/<token>/
    """

    # Type hints for reverse relations
    rel_view_projects: models.QuerySet[GISViewProject]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        help_text="Descriptive name for this GIS view",
    )

    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of what this view contains",
    )

    gis_token = models.CharField(
        "GIS View Token",
        max_length=40,
        unique=True,
        blank=False,
        null=False,
        default=generate_random_token,
        db_index=True,
        help_text="Unique token for API access to this view",
    )

    owner = models.ForeignKey(
        User,
        related_name="owned_gis_views",
        on_delete=models.CASCADE,
        help_text="User who owns and can manage this view",
    )

    projects = models.ManyToManyField(  # type: ignore[var-annotated]
        Project,
        through="GISViewProject",
        related_name="rel_gis_views",
        help_text="Projects included in this view",
    )

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "GIS View"
        verbose_name_plural = "GIS Views"
        ordering = ["-modified_date"]
        indexes = [
            models.Index(fields=["owner"]),
            models.Index(fields=["gis_token"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.gis_token[:8]}...)"

    def save(
        self,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Validate before saving."""
        self.full_clean()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
            **kwargs,
        )

    def regenerate_token(self) -> None:
        """Generate a new access token for this view."""
        self.gis_token = generate_random_token()
        self.save(update_fields=["gis_token", "modified_date"])

    def get_geojson_urls(self, expires_in: int = 3600) -> list[dict[str, Any]]:
        """
        Get all GeoJSON signed URLs for projects in this view.

        Uses optimized prefetch to avoid N+1 queries.

        Args:
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            List of dicts containing project info and signed URLs
        """

        # Optimize: prefetch GeoJSON to avoid N+1 queries
        view_projects = self.rel_view_projects.select_related(
            "project"
        ).prefetch_related(
            Prefetch(
                "project__rel_geojsons",
                queryset=ProjectGeoJSON.objects.order_by("-creation_date"),
            )
        )

        results = []

        for view_project in view_projects:
            project = view_project.project
            geojson = None

            # Get the appropriate GeoJSON
            if view_project.use_latest:
                # Use prefetched data (already ordered by -creation_date)
                geojsons = list(project.rel_geojsons.all())
                if not geojsons:
                    continue
                geojson = geojsons[0]  # First is latest
            elif view_project.commit_sha:
                # Find in prefetched data
                geojsons = list(project.rel_geojsons.all())
                geojson = next(
                    (g for g in geojsons if g.commit_sha == view_project.commit_sha),
                    None,
                )
                if not geojson:
                    continue
            else:
                # Neither use_latest nor commit_sha - skip
                continue

            try:
                results.append(
                    {
                        "project_id": str(project.id),
                        "project_name": project.name,
                        "commit_sha": geojson.commit_sha,
                        "commit_date": geojson.commit_date.isoformat(),
                        "url": geojson.get_signed_download_url(expires_in=expires_in),
                        "use_latest": view_project.use_latest,
                    }
                )
            except (ValidationError, Exception):  # noqa: BLE001
                logger.exception(
                    "Error generating signed URL for project %s in view %s",
                    project.id,
                    self.id,
                )
                continue

        return results


class GISViewProject(models.Model):
    """
    Through model linking GIS Views to Projects with commit selection.

    Represents the configuration for a single project within a GIS view,
    specifying either a specific commit SHA or using the latest commit.
    """

    gis_view = models.ForeignKey(
        GISView,
        related_name="rel_view_projects",
        on_delete=models.CASCADE,
    )

    project = models.ForeignKey(
        Project,
        related_name="rel_gis_view_projects",
        on_delete=models.CASCADE,
    )

    commit_sha = models.CharField(
        max_length=40,
        blank=True,
        default="",
        help_text="Specific commit SHA (40 hex chars). Leave empty if using latest.",
    )

    use_latest = models.BooleanField(
        default=False,
        help_text=(
            "If True, always use the latest commit. Takes precedence over commit_sha."
        ),
    )

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "GIS View Project"
        verbose_name_plural = "GIS View Projects"
        unique_together = [("gis_view", "project")]
        ordering = ["creation_date"]
        indexes = [
            models.Index(fields=["gis_view", "project"]),
        ]
        constraints = [
            # Must specify either use_latest=True OR commit_sha
            models.CheckConstraint(
                condition=(
                    Q(use_latest=True) | Q(commit_sha__isnull=False, commit_sha__gt="")
                ),
                name="gisview_must_specify_commit_or_latest",
            ),
        ]

    def __str__(self) -> str:
        commit_info = (
            "latest"
            if self.use_latest
            else (self.commit_sha[:8] if self.commit_sha else "unspecified")
        )
        return f"{self.gis_view.name} → {self.project.name} @ {commit_info}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Validate before saving."""
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Validate the model before saving."""
        super().clean()

        # If use_latest is True, clear commit_sha (takes precedence)
        if self.use_latest and self.commit_sha:
            self.commit_sha = ""

        # Validate commit_sha format if provided
        if self.commit_sha:
            self.commit_sha = self.commit_sha.strip().lower()

            if not bool(sha1_regex.fullmatch(self.commit_sha)):
                raise ValidationError({"commit_sha": "Commit SHA is not valid"})

        # Ensure either use_latest or commit_sha is set
        if not self.use_latest and not self.commit_sha:
            raise ValidationError(
                "Either use_latest must be True or commit_sha must be provided"
            )
