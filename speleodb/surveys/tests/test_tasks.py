"""Exercise operations task delivery without running against development data."""

from __future__ import annotations

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings

from speleodb.surveys.tasks import refresh_project_geojson
from speleodb.utils.exceptions import reraise_task_timeout


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


def test_project_rebuild_has_explicit_limits_and_manual_recovery_policy() -> None:
    assert (
        refresh_project_geojson.soft_time_limit
        == settings.GEOJSON_REBUILD_SOFT_TIME_LIMIT
    )
    assert (
        refresh_project_geojson.time_limit == settings.GEOJSON_REBUILD_HARD_TIME_LIMIT
    )
    assert refresh_project_geojson.track_started is False
    assert refresh_project_geojson.acks_late is False
    assert refresh_project_geojson.reject_on_worker_lost is False
    assert refresh_project_geojson.max_retries == 0
