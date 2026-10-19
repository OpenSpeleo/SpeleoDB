# -*- coding: utf-8 -*-

"""drf-spectacular preprocessing hooks.

Referenced from ``SPECTACULAR_SETTINGS['PREPROCESSING_HOOKS']`` in
``config/settings/base.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from collections.abc import Callable


def exclude_legacy_v1_paths(
    endpoints: list[tuple[str, str, str, Callable[..., Any]]],
    **_kwargs: Any,
) -> list[tuple[str, str, str, Callable[..., Any]]]:
    """Exclude obsolete SpeleoDB v1 routes from the supported SDK contract.

    The backend retains its legacy middleware and mounts for compatibility.
    Authentication's /v1 protocol routes are supported and remain documented.
    """
    return [
        endpoint for endpoint in endpoints if not endpoint[0].startswith("/api/v1/")
    ]
