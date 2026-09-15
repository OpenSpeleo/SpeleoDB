# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import math
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
    max_delay: float = 30.0,
    sleep_fn: Callable[[float], None] | None = None,
    log_error_details: bool = True,
    **fn_kwargs: Any,
) -> RT:
    """Call *fn* up to *retries* times with exponential backoff.

    On each transient failure matching *exc_types*, sleeps for
    ``base_delay * backoff_factor ** attempt`` seconds, capped at *max_delay*,
    before retrying. *retries* includes the first attempt. Raises the last
    exception if all attempts are exhausted, without sleeping after it.
    """
    if isinstance(retries, bool) or not isinstance(retries, int) or retries < 1:
        raise ValueError("retries must be a positive integer")
    if not math.isfinite(base_delay) or base_delay < 0:
        raise ValueError("base_delay must be finite and nonnegative")
    if not math.isfinite(backoff_factor) or backoff_factor < 1:
        raise ValueError("backoff_factor must be finite and at least one")
    if not math.isfinite(max_delay) or max_delay < 0:
        raise ValueError("max_delay must be finite and nonnegative")

    delay: float = min(base_delay, max_delay)
    last_exc: BaseException | None = None
    for attempt in range(retries):
        try:
            return fn(*fn_args, **fn_kwargs)
        except exc_types as exc:
            last_exc = exc
            if attempt + 1 == retries:
                raise
            logger.debug(
                "Retry %d/%d for %s after %.2fs: %s",
                attempt + 1,
                retries,
                getattr(fn, "__qualname__", fn),
                delay,
                exc if log_error_details else type(exc).__name__,
            )
            (time.sleep if sleep_fn is None else sleep_fn)(delay)
            # Iteration avoids computing an arbitrarily large exponent when a
            # caller increases the attempt budget.
            delay = min(delay * backoff_factor, max_delay)

    # Unreachable, but keeps type checkers happy
    raise RuntimeError("retry_with_backoff exhausted") from last_exc
