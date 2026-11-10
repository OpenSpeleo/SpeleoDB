"""Exercise operations task delivery without running against development data."""

from __future__ import annotations

import os
import signal
import sys
from typing import TYPE_CHECKING

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from compass_lib.io import load_project
from django.conf import settings
from openspeleo_lib.interfaces import ArianeInterface
from openspeleo_lib.interfaces import StalagMightInterface

from speleodb.common.enums import ProjectType
from speleodb.surveys.models import Project
from speleodb.surveys.tasks import refresh_project_geojson
from speleodb.testing.stalagmight import stalagmight_bytes
from speleodb.utils.exceptions import reraise_task_timeout

if TYPE_CHECKING:
    from pathlib import Path
    from types import FrameType


@pytest.mark.parametrize(
    ("project_type", "filename"),
    [
        (ProjectType.ARIANE, "test_simple.tml"),
        (ProjectType.COMPASS, "sample.mak"),
        (ProjectType.STALAGMIGHT, "native.stalx"),
    ],
)
def test_source_timeout_is_not_treated_as_invalid_survey(
    project_type: ProjectType, filename: str, tmp_path: Path
) -> None:
    source = (
        settings.BASE_DIR / "speleodb" / "api" / "v2" / "tests" / "artifacts" / filename
    )
    if project_type == ProjectType.STALAGMIGHT:
        source = tmp_path / filename
        source.write_bytes(stalagmight_bytes())
    loader_code = {
        ProjectType.ARIANE: ArianeInterface.from_file.__code__,
        ProjectType.COMPASS: load_project.__code__,
        ProjectType.STALAGMIGHT: StalagMightInterface.from_file.__code__,
    }[project_type]
    signal_delivered = False

    def soft_timeout(_signum: int, _frame: FrameType | None) -> None:
        nonlocal signal_delivered
        signal_delivered = True
        raise SoftTimeLimitExceeded

    def observe_loader(frame: FrameType, event: str, _argument: object) -> None:
        if event == "call" and frame.f_code is loader_code and not signal_delivered:
            os.kill(os.getpid(), signal.SIGUSR1)

    # Observe the actual loader entry while build_geojson's exception handler is
    # active. A real OS signal interrupts conversion without replacing a parser
    # or relying on file-open events from Ariane's native reader.
    previous_profile = sys.getprofile()
    previous_handler = signal.signal(signal.SIGUSR1, soft_timeout)
    try:
        sys.setprofile(observe_loader)
        with pytest.raises(SoftTimeLimitExceeded):
            Project(type=project_type).build_geojson(source)
        assert signal_delivered
    finally:
        sys.setprofile(previous_profile)
        signal.signal(signal.SIGUSR1, previous_handler)
    assert sys.getprofile() is previous_profile
    assert signal.getsignal(signal.SIGUSR1) == previous_handler


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
