"""Exercise maintenance task delivery without running against development data."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from celery.contrib.testing.worker import start_worker
from celery.exceptions import SoftTimeLimitExceeded
from celery.result import EagerResult
from django.conf import settings

from config.celery_app import app
from speleodb.common.enums import ProjectType
from speleodb.surveys.models import Project
from speleodb.surveys.tasks import refresh_all_projects_geojson
from speleodb.utils.exceptions import reraise_task_timeout

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("project_type", "loader"),
    [
        (ProjectType.ARIANE, "ArianeInterface.from_file"),
        (ProjectType.COMPASS, "load_project"),
    ],
)
def test_source_timeout_is_not_treated_as_invalid_survey(
    project_type: ProjectType, loader: str, tmp_path: Path
) -> None:
    project = Project(type=project_type)
    with (
        patch(
            f"speleodb.surveys.models.project.{loader}",
            side_effect=SoftTimeLimitExceeded,
        ),
        pytest.raises(SoftTimeLimitExceeded),
    ):
        project.build_geojson(tmp_path / "source")


def test_compass_coordinate_conversion_preserves_wrapped_timeout() -> None:
    source = (
        settings.BASE_DIR
        / "speleodb"
        / "api"
        / "v2"
        / "tests"
        / "artifacts"
        / "sample.mak"
    )
    project = Project(type=ProjectType.COMPASS)
    with (
        patch(
            "compass_lib.geojson._get_transformer", side_effect=SoftTimeLimitExceeded
        ),
        pytest.raises(SoftTimeLimitExceeded),
    ):
        project.build_geojson(source)


@pytest.mark.parametrize("chain_attribute", ["__cause__", "__context__"])
def test_nested_timeout_is_preserved(chain_attribute: str) -> None:
    timeout = SoftTimeLimitExceeded()
    wrapper = ValueError("Conversion interrupted")
    setattr(wrapper, chain_attribute, timeout)
    outer = RuntimeError("Export failed")
    setattr(outer, chain_attribute, wrapper)
    with pytest.raises(SoftTimeLimitExceeded) as raised:
        reraise_task_timeout(outer)
    assert raised.value is timeout


def test_ordinary_error_cycles_do_not_prevent_batch_error_isolation() -> None:
    error = ValueError("Invalid survey")
    wrapper = RuntimeError("Conversion failed")
    error.__cause__ = wrapper
    wrapper.__context__ = error
    reraise_task_timeout(error)


@pytest.mark.django_db(transaction=True)
def test_geojson_rebuild_is_consumed_asynchronously_and_empty_scope_is_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert not Project.objects.exists()
    monkeypatch.setattr(app.conf, "task_always_eager", False)
    queue = f"test-geojson-rebuild-{uuid.uuid4().hex}"
    with start_worker(app, queues=[queue], perform_ping_check=False):
        result = refresh_all_projects_geojson.apply_async(queue=queue)
        assert not isinstance(result, EagerResult)
        assert result.get(timeout=15) is None
        assert result.successful()
    assert not Project.objects.exists()


def test_geojson_rebuild_has_maintenance_limits_instead_of_request_limits() -> None:
    assert (
        refresh_all_projects_geojson.soft_time_limit
        == settings.GEOJSON_REBUILD_SOFT_TIME_LIMIT
    )
    assert refresh_all_projects_geojson.time_limit == (
        settings.GEOJSON_REBUILD_HARD_TIME_LIMIT
    )
    assert (
        0
        < settings.GEOJSON_REBUILD_SOFT_TIME_LIMIT
        < (settings.GEOJSON_REBUILD_HARD_TIME_LIMIT)
    )
