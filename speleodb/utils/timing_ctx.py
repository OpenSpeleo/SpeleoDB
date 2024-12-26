#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager

from django.conf import settings

logger = logging.getLogger(__name__)


@contextmanager
def timed_section(section_name: str) -> Generator[None, None, None]:
    if not settings.DEBUG:
        yield

    else:
        if not hasattr(timed_section, "_indentation_level"):
            # Initialize static variable
            timed_section._indentation_level = 0  # noqa: SLF001

        current_indent = "\t" * timed_section._indentation_level  # noqa: SLF001

        try:
            logging.info(f"{current_indent}[TIMED SECTION START] `{section_name}` ...")
            start_t = time.perf_counter()
            # Increase indentation for nested calls
            timed_section._indentation_level += 1  # noqa: SLF001
            yield
        finally:
            # Decrease indentation on exit
            timed_section._indentation_level -= 1  # noqa: SLF001
            total_t = time.perf_counter() - start_t
            current_indent = "\t" * timed_section._indentation_level  # noqa: SLF001
            logging.info(
                f"{current_indent}[TIMED SECTION END]   Total: {total_t:0.2f} secs ..."
            )
