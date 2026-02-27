# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import re
import uuid
from typing import TYPE_CHECKING
from typing import Any

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

logger = logging.getLogger(__name__)

sha1_regex = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


class GISView(models.Model):
    """
    A GIS View represents a curated collection of project GeoJSON data.

    Each view has a unique token that allows unauthenticated access to
    the specified projects and commits via a public API endpoint.
    """

    # Type hints for reverse relations
    project_views: models.QuerySet[GISProjectView]

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

    allow_precise_zoom = models.BooleanField(
        help_text="If True, allows users to zoom to the precise location of the cave",
    )

    gis_token = models.CharField(
        "GIS View Token",
        max_length=40,
        unique=True,
        blank=False,
        null=False,
        default=generate_random_token,
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
        through="GISProjectView",
        related_name="gis_views",
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
            # models.Index(fields=["gis_token"]),  # Present via unique constraint
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

    def get_view_geojson_data(self) -> list[dict[str, Any]]:
        """
        Get all GeoJSON signed URLs for projects in this view.

        Uses optimized prefetch to avoid N+1 queries.

        Args:
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            List of dicts containing project info and signed URLs
        """

        project_views = self.project_views.select_related("project").prefetch_related(
            Prefetch(
                "project__geojsons",
                queryset=ProjectGeoJSON.objects.select_related("commit").order_by(
                    "-commit__authored_date"
                ),
            )
        )

        results = []

        for view_project in project_views:
            project: Project = view_project.project

            proj_geojson: ProjectGeoJSON

            if view_project.use_latest:
                if (geojson := project.geojsons.first()) is None:
                    continue

                proj_geojson = geojson

            elif view_project.commit_sha:
                matched = project.geojsons.filter(
                    commit_id=view_project.commit_sha
                ).first()

                if matched is None:
                    continue

                proj_geojson = matched

            else:
                logger.error(
                    "GISProjectView %s has neither use_latest nor commit_sha set",
                    view_project.id,
                )
                continue

            results.append(
                {
                    "project_id": str(project.id),
                    "project_name": project.name,
                    "project_geojson": proj_geojson,
                    "commit_sha": proj_geojson.commit.id,
                    "commit_date": proj_geojson.commit.authored_date.isoformat(),
                    "use_latest": view_project.use_latest,
                }
            )

        return results

    def get_geojson_urls(self, expires_in: int = 3600) -> list[dict[str, Any]]:
        """
        Get all GeoJSON signed URLs for projects in this view.

        Uses optimized prefetch to avoid N+1 queries.

        Args:
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            List of dicts containing project info and signed URLs
        """

        data = self.get_view_geojson_data()

        result = []

        for geojson_data in data:
            try:
                geojson_data["url"] = geojson_data.pop(
                    "project_geojson"
                ).get_signed_download_url(expires_in=expires_in)

            except ValidationError, Exception:
                logger.exception(
                    "Error generating signed URL for project %s in view %s",
                    geojson_data["project_id"],
                    self.id,
                )
                continue

            result.append(geojson_data)

        return result


class GISProjectView(models.Model):
    """
    Through model linking GISViews to Projects with commit selection.

    Represents the configuration for a single project within a GISView,
    specifying either a specific commit SHA or using the latest commit.
    """

    id: int

    gis_view = models.ForeignKey(
        GISView,
        related_name="project_views",
        on_delete=models.CASCADE,
    )

    project = models.ForeignKey(
        Project,
        related_name="project_views",
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
        verbose_name = "GIS Project View"
        verbose_name_plural = "GIS Project Views"
        ordering = ["creation_date"]
        indexes = [
            models.Index(fields=["gis_view"])
            # models.Index(fields=["gis_view", "project"]), # present via unique_together  # noqa: E501
        ]
        constraints = [
            # Must specify either use_latest=True OR commit_sha
            models.CheckConstraint(
                condition=(
                    Q(use_latest=True) | Q(commit_sha__isnull=False, commit_sha__gt="")
                ),
                name="gisview_must_specify_commit_or_latest",
            ),
            models.UniqueConstraint(
                fields=["gis_view", "project"],
                name="%(app_label)s_%(class)s_project_gis_view_unique",
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
