#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import time
from types import TracebackType

from django.conf import settings

logger = logging.getLogger(__name__)


# @contextmanager
# def timed_section(section_name: str) -> Generator[None]:
class timed_section:  # noqa: N801
    _indentation_level: int = 0
    section_name: str
    start_t: float | None = None

    def __init__(self, section_name: str) -> None:
        self.section_name = section_name

    def __enter__(self) -> None:
        if not settings.DEBUG:
            return

        # We increment after for the next call
        logging.info(
            f"{self.indent_prefix}[TIMED SECTION START] `{self.section_name}` ..."
        )
        timed_section._indentation_level += 1

        self.start_t = time.perf_counter()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if settings.DEBUG and self.start_t is not None:
            # Decrease indentation on exit
            timed_section._indentation_level -= 1
            total_t = time.perf_counter() - self.start_t
            logging.info(
                f"{self.indent_prefix}[TIMED SECTION END]   Total: {total_t:0.2f} "
                "secs ..."
            )

    @property
    def indent_prefix(self) -> str:
        return "\t" * timed_section._indentation_level
