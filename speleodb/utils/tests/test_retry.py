from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import pytest

from speleodb.utils.helpers import retry_with_backoff

if TYPE_CHECKING:
    from pathlib import Path


def test_retry_stops_immediately_after_success(tmp_path: Path) -> None:
    source = tmp_path / "ready"
    source.write_text("ready")
    attempts = 0

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        return source.read_text()

    assert retry_with_backoff(operation, base_delay=0.001) == "ready"
    assert attempts == 1


def test_retry_stops_after_only_attempt(tmp_path: Path) -> None:
    attempts = 0
    missing_file = tmp_path / "missing"

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        missing_file.read_bytes()

    with pytest.raises(FileNotFoundError):
        retry_with_backoff(operation, retries=1)

    assert attempts == 1


@pytest.mark.parametrize(
    "options",
    [
        {"retries": 0},
        {"retries": -1},
        {"retries": True},
        {"base_delay": float("inf")},
        {"base_delay": float("nan")},
        {"base_delay": -1.0},
        {"backoff_factor": float("inf")},
        {"backoff_factor": 0.5},
        {"max_delay": float("inf")},
        {"max_delay": -1.0},
    ],
)
def test_retry_rejects_invalid_limits_before_calling_operation(
    options: dict[str, Any],
) -> None:
    called = False

    def operation() -> None:
        nonlocal called
        called = True

    with pytest.raises(ValueError, match="must be"):
        retry_with_backoff(operation, **options)

    assert not called
