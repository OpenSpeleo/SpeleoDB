# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from typing import TYPE_CHECKING
from typing import Any

from django.utils import timezone

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


def get_timestamp() -> str:
    return timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")


def maybe_sort_data[T](data: T) -> OrderedDict[str, Any] | list[Any] | T:
    match data:
        case dict():
            return OrderedDict(
                {key: maybe_sort_data(val) for key, val in sorted(data.items())}
            )

        case tuple() | list():
            return [maybe_sort_data(_data) for _data in data]

    return data


def str2bool(v: str) -> bool:
    if not isinstance(v, str):
        raise TypeError(f"Expected `str`, received: `{type(v)}`")
    return v.lower() in [
        "true",
        "1",
        "t",
        "y",
        "yes",
        "yeah",
        "yup",
        "certainly",
        "uh-huh",
    ]


def retry_with_backoff[RT](
    fn: Callable[..., RT],
    *fn_args: Any,
    retries: int = 5,
    exc_types: tuple[type[BaseException], ...] = (Exception,),
    base_delay: float = 0.1,
    backoff_factor: float = 2.0,
    **fn_kwargs: Any,
) -> RT:
    """Call *fn* up to *retries* times with exponential backoff.

    On each transient failure matching *exc_types*, sleeps for
    ``base_delay * backoff_factor ** attempt`` seconds before
    retrying. Raises the last exception if all attempts are exhausted.
    """
    last_exc: BaseException | None = None
    for attempt in range(retries):
        try:
            return fn(*fn_args, **fn_kwargs)
        except exc_types as exc:
            last_exc = exc
            if attempt + 1 == retries:
                raise
            delay = base_delay * (backoff_factor**attempt)
            logger.debug(
                "Retry %d/%d for %s after %.2fs: %s",
                attempt + 1,
                retries,
                getattr(fn, "__qualname__", fn),
                delay,
                exc,
            )
            time.sleep(delay)

    # Unreachable, but keeps type checkers happy
    raise RuntimeError("retry_with_backoff exhausted") from last_exc
