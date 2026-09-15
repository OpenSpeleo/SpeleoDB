from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from speleodb.utils.helpers import retry_with_backoff


@patch("speleodb.utils.helpers.time", autospec=True)
def test_retry_stops_at_attempt_budget_with_capped_exponential_backoff(
    mock_time: MagicMock,
) -> None:
    failure = ConnectionError("unavailable")
    operation = MagicMock(side_effect=failure)

    with pytest.raises(ConnectionError) as error:
        retry_with_backoff(
            operation,
            retries=6,
            exc_types=(ConnectionError,),
            base_delay=1.0,
            max_delay=4.0,
        )

    assert error.value is failure
    assert operation.call_count == 6  # noqa: PLR2004
    assert [call.args[0] for call in mock_time.sleep.call_args_list] == [1, 2, 4, 4, 4]


@patch("speleodb.utils.helpers.time", autospec=True)
def test_retry_stops_immediately_after_success(mock_time: MagicMock) -> None:
    operation = MagicMock(side_effect=[ConnectionError("unavailable"), "ready"])

    assert retry_with_backoff(operation, base_delay=0.25) == "ready"
    assert operation.call_count == 2  # noqa: PLR2004
    mock_time.sleep.assert_called_once_with(0.25)


@patch("speleodb.utils.helpers.time", autospec=True)
def test_retry_does_not_sleep_after_only_attempt(mock_time: MagicMock) -> None:
    operation = MagicMock(side_effect=ConnectionError("unavailable"))

    with pytest.raises(ConnectionError):
        retry_with_backoff(operation, retries=1)

    operation.assert_called_once_with()
    mock_time.sleep.assert_not_called()


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
    operation = MagicMock()

    with pytest.raises(ValueError, match="must be"):
        retry_with_backoff(operation, **options)

    operation.assert_not_called()


@patch("speleodb.utils.helpers.time", autospec=True)
def test_retry_caps_growth_without_exponent_overflow(mock_time: MagicMock) -> None:
    operation = MagicMock(side_effect=ConnectionError("unavailable"))

    with pytest.raises(ConnectionError):
        retry_with_backoff(
            operation,
            retries=4,
            base_delay=1.0,
            backoff_factor=1e308,
            max_delay=2.0,
        )

    assert [call.args[0] for call in mock_time.sleep.call_args_list] == [1.0, 2.0, 2.0]
