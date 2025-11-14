# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def format_coordinate(value: Any) -> float:
    """Format a coordinate value to 7 decimal places"""
    return round(float(value), 7)


def maybe_convert_dms_to_decimal(value: str) -> str | float:
    """
    Convert DMS coordinate string (e.g. '30°15'03"N' or '30° 15' 03" N') to decimal
    degrees.
    Supports optional spaces and N/S/E/W suffix for direction.
    """
    # Regex pattern allowing optional spaces between components
    pattern = r"""
        ^\s*
        (\d+)\s*°\s*        # degrees
        (\d+)\s*'\s*        # minutes
        (\d+(?:\.\d+)?)\s*"?\s*  # seconds (can have decimals)
        ([NSEW])             # direction
        \s*$
    """
    match = re.match(pattern, value.strip(), re.VERBOSE | re.IGNORECASE)

    if not match:
        return value

    degrees, minutes, seconds, direction = match.groups()
    decimal = int(degrees) + int(minutes) / 60 + float(seconds) / 3600

    # South and West should be negative
    if direction.upper() in ("S", "W"):
        decimal = -decimal

    return decimal
