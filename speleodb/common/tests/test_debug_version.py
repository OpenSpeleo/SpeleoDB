from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest
from django.template import Context
from django.template import Template
from django.utils import timezone

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("clock_timezone", ["UTC", "America/Cancun"])
def test_debug_version_uses_django_clock_only_in_debug(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    debug: bool,
    clock_timezone: str,
) -> None:
    settings.DEBUG = debug
    now: datetime = datetime(2000, 1, 1, microsecond=999999, tzinfo=UTC).astimezone(
        ZoneInfo(clock_timezone)
    )
    monkeypatch.setattr(timezone, "now", lambda: now)
    template: Template = Template("{% load debug_version %}{% maybe_debug_version %}")
    assert template.render(Context()) == ("?v=946684800" if debug else "")
