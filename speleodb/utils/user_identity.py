"""Shared account-name invariant and fallback for legacy Git authors."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError

DEFAULT_USER_NAME: str = "NO NAME"

# Python's Unicode whitespace set, explicitly spelled out for identical SQLite
# and PostgreSQL regex behavior (their locale-dependent \s classes differ).
USER_NAME_NONBLANK_PATTERN: str = (
    "[^\t-\r\x1c- \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]"
)
_NONBLANK_NAME: re.Pattern[str] = re.compile(USER_NAME_NONBLANK_PATTERN)


def has_user_name(value: str | None) -> bool:
    """Whether a name contains at least one non-whitespace character."""
    return isinstance(value, str) and _NONBLANK_NAME.search(value) is not None


def validate_user_name(value: str | None) -> None:
    """Require a name without changing international names or punctuation."""
    if not has_user_name(value):
        raise ValidationError("A name is required.", code="blank")
