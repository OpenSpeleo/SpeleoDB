"""Read the inert controller configuration delivered by a rendered Django page."""

from __future__ import annotations

import json
import re


def _unique_fields(fields: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = dict(fields)
    assert len(result) == len(fields), "Controller JSON contains duplicate keys"
    return result


def controller_context(html: str, controller: str) -> dict[str, object]:
    matches: list[str] = re.findall(
        rf'<script\b[^>]*data-speleodb-controller="{re.escape(controller)}"[^>]*>'
        r"(.*?)</script>",
        html,
        re.DOTALL,
    )
    assert len(matches) == 1, f"Expected one {controller} controller"
    context: dict[str, object] = json.loads(
        matches[0], object_pairs_hook=_unique_fields
    )
    assert isinstance(context, dict), "Controller configuration must be an object"
    return context
