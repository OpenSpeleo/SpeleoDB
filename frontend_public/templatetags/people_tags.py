# -*- coding: utf-8 -*-
"""Template tags for people display grid layout."""

from __future__ import annotations

from typing import Any

from django import template

# ruff: noqa: PLR2004

register = template.Library()


@register.filter
def get_grid_class(total_count: int) -> str:
    """
    Return appropriate grid class based on optimal layout calculation.

    Algorithm:
    - Calculate completeness score for 2-column and 3-column layouts
    - Choose layout that minimizes incomplete rows and total rows
    """
    if total_count <= 2:
        # 1 or 2 people always use 2 columns
        return "grid-cols-1 md:grid-cols-2"

    # Calculate layout metrics for 2 and 3 columns
    rows_2col = (total_count + 1) // 2  # Ceiling division
    remainder_2col = total_count % 2

    rows_3col = (total_count + 2) // 3  # Ceiling division
    remainder_3col = total_count % 3

    # Score based on: fewer rows is better, complete rows are better
    # Penalty for incomplete rows (0 remainder is best)
    score_2col = rows_2col + (0.5 if remainder_2col == 1 else 0)
    score_3col = rows_3col + (
        0.3 if remainder_3col == 1 else 0.6 if remainder_3col == 2 else 0
    )

    # For small numbers (3-6), prefer 2 columns unless 3 divides evenly
    if total_count <= 6:
        if total_count % 3 == 0:  # 3 or 6 people
            return "grid-cols-1 md:grid-cols-2 lg:grid-cols-3"
        return "grid-cols-1 md:grid-cols-2"

    # For larger numbers, use scoring algorithm
    if score_2col <= score_3col:
        return "grid-cols-1 md:grid-cols-2"
    return "grid-cols-1 md:grid-cols-2 lg:grid-cols-3"


@register.filter
def get_grid_cols(total_count: int) -> int:
    """Return the number of columns for the grid at largest breakpoint."""
    grid_class = get_grid_class(total_count)
    return 3 if "lg:grid-cols-3" in grid_class else 2


@register.filter
def needs_centering(people_list: list[Any]) -> bool:
    """Check if last row needs centering based on optimal grid."""
    total = len(people_list)
    cols = get_grid_cols(total)
    remainder = total % cols
    return remainder > 0


@register.filter
def last_row_offset_class(people_list: list[Any]) -> str:
    """Return the appropriate offset class for centering the last row."""
    total = len(people_list)
    cols = get_grid_cols(total)
    remainder = total % cols

    if remainder == 0:
        return ""

    if cols == 2 and remainder == 1:
        return "md:col-start-2"  # Center single item in 2-col grid
    if cols == 3:
        if remainder == 1:
            return "lg:col-start-2"  # Center single item in 3-col grid
        if remainder == 2:
            return "lg:col-start-1"  # No offset needed for 2 items in 3-col grid

    return ""


@register.filter
def is_last_row_item(forloop_counter: int, people_list: list[Any]) -> bool:
    """Check if current item is in the last row."""
    total = len(people_list)
    cols = get_grid_cols(total)
    remainder = total % cols

    if remainder == 0:
        # Last row is complete
        return forloop_counter > total - cols
    # Last row is incomplete
    return forloop_counter > total - remainder


@register.filter
def should_apply_offset(forloop_counter: int, people_list: list[Any]) -> bool:
    """Check if current item should have the offset class applied."""
    total = len(people_list)
    cols = get_grid_cols(total)
    remainder = total % cols

    if remainder == 0:
        return False

    # Only the first item in the last row should have the offset
    first_item_in_last_row = total - remainder + 1
    return forloop_counter == first_item_in_last_row
