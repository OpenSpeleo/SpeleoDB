from __future__ import annotations

from datetime import UTC
from datetime import datetime

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from speleodb.common.management.commands.wipe_test_gitlab import is_older_than


@pytest.mark.parametrize(
    ("created_at", "expected"),
    [
        ("2026-09-14T09:59:59Z", True),
        ("2026-09-14T05:59:59-04:00", True),
        ("2026-09-14T10:00:00Z", False),
        ("2026-09-15T09:00:00Z", False),
        ("2026-09-14T09:00:00", False),
        ("2026-99-14T09:00:00Z", False),
        ("invalid", False),
        (None, False),
    ],
)
def test_cleanup_requires_verified_stale_creation_date(
    created_at: object, expected: bool
) -> None:
    cutoff: datetime = datetime(2026, 9, 14, 10, tzinfo=UTC)
    assert is_older_than(created_at, cutoff) is expected


@pytest.mark.parametrize("hours", [0, -1])
def test_cleanup_rejects_nonpositive_age_before_contacting_gitlab(hours: int) -> None:
    with pytest.raises(CommandError, match="must be positive"):
        call_command("wipe_test_gitlab", older_than_hours=hours)
