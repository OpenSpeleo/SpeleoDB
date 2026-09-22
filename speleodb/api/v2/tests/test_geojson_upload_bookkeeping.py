"""Optional post-push bookkeeping never executes conversion or broker I/O."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from django.db import transaction
from django.utils import timezone

from speleodb.api.v2.views.file import request_uploaded_geojson
from speleodb.common.enums import ProjectType
from speleodb.gis.models import ProjectGeoJSONGeneration
from speleodb.surveys.models import ProjectCommit

if TYPE_CHECKING:
    from speleodb.surveys.models import Project


@pytest.fixture
def source(project: Project) -> ProjectCommit:
    project.type = ProjectType.ARIANE
    project.exclude_geojson = False
    project.save(update_fields=["type", "exclude_geojson"])
    return ProjectCommit.objects.create(
        pk="a" * 40,
        project=project,
        author_name="Surveyor",
        author_email="survey@example.org",
        authored_date=timezone.now(),
        message="Saved source",
    )


@pytest.mark.django_db
def test_request_records_only_and_rollback_discards_pending_job(
    source: ProjectCommit,
) -> None:
    with (
        patch("celery.current_app.send_task", side_effect=AssertionError("broker")),
        patch(
            "openspeleo_lib.interfaces.ArianeInterface.from_file",
            side_effect=AssertionError("parser"),
        ),
        transaction.atomic(),
    ):
        assert (
            request_uploaded_geojson(source.project, source.pk, [Path("ariane.tml")])
            == "pending"
        )
        assert ProjectGeoJSONGeneration.objects.filter(commit=source).exists()
        transaction.set_rollback(True)
    assert not ProjectGeoJSONGeneration.objects.filter(commit=source).exists()


@pytest.mark.django_db
def test_unrelated_upload_does_not_schedule(source: ProjectCommit) -> None:
    assert (
        request_uploaded_geojson(source.project, source.pk, [Path("notes.pdf")])
        == "not_requested"
    )
    assert not ProjectGeoJSONGeneration.objects.filter(commit=source).exists()


@pytest.mark.django_db
def test_reporting_failure_cannot_change_upload_outcome(source: ProjectCommit) -> None:
    with (
        patch(
            "speleodb.api.v2.views.file.request_geojson_generation",
            side_effect=RuntimeError("optional bookkeeping"),
        ),
        patch(
            "speleodb.api.v2.views.file.sentry_sdk.capture_exception",
            side_effect=RuntimeError("reporting unavailable"),
        ),
    ):
        assert (
            request_uploaded_geojson(source.project, source.pk, [Path("ariane.tml")])
            == "unavailable"
        )
    assert ProjectCommit.objects.filter(pk=source.pk).exists()
