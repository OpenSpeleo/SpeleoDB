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
    """Drop the legacy ``/api/v1/`` mirror routes from the OpenAPI schema.

    ``/api/v1/`` is a backward-compatibility alias that reuses the same v2
    view classes (see ``speleodb/api_router.py``) but is wrapped by
    ``DRFWrapResponseMiddleware``. Because the two namespaces share
    identical callables, drf-spectacular would emit ``operationId``
    collision warnings for every shared endpoint. The canonical
    documented surface is ``/api/v2/``, so the legacy mirror is excluded
    from the schema entirely.
    """
    return [
        endpoint for endpoint in endpoints if not endpoint[0].startswith("/api/v1/")
    ]
