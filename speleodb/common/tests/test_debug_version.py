from __future__ import annotations

from typing import TYPE_CHECKING

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
    debug: bool,
    clock_timezone: str,
) -> None:
    settings.DEBUG = debug
    template: Template = Template("{% load debug_version %}{% maybe_debug_version %}")
    with timezone.override(clock_timezone):
        before = int(timezone.now().timestamp())
        rendered = template.render(Context())
        after = int(timezone.now().timestamp())
    if debug:
        assert rendered.startswith("?v=")
        assert before <= int(rendered.removeprefix("?v=")) <= after
    else:
        assert rendered == ""
