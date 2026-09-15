"""Exercise the entrypoint's readiness function without starting containers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

import psycopg
import pytest

from compose.wait_for_postgres import wait_for_postgres

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def readiness_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[MagicMock]:
    for name, value in {
        "POSTGRES_DB": "test-database",
        "POSTGRES_USER": "test-user",
        "POSTGRES_PASSWORD": "test-password'\\\"",
        "POSTGRES_HOST": "database.invalid",
        "POSTGRES_PORT": "5432",
    }.items():
        monkeypatch.setenv(name, value)
    with patch("psycopg.connect") as connect:
        yield connect


def test_database_readiness_uses_connection_timeout_and_closes_connection(
    readiness_connection: MagicMock,
) -> None:
    with patch("time.sleep") as sleep:
        wait_for_postgres()

    readiness_connection.assert_called_once_with(
        dbname="test-database",
        user="test-user",
        password="test-password'\\\"",  # noqa: S106 - Fixture tests shell quoting.
        host="database.invalid",
        port="5432",
        connect_timeout=5,
    )
    readiness_connection.return_value.__exit__.assert_called_once()
    sleep.assert_not_called()


def test_database_readiness_recovers_with_exponential_waits(
    readiness_connection: MagicMock,
) -> None:
    connected: MagicMock = MagicMock()
    readiness_connection.side_effect = [
        psycopg.OperationalError("unavailable"),
        psycopg.OperationalError("unavailable"),
        connected,
    ]
    with patch("time.sleep") as sleep:
        wait_for_postgres()

    assert readiness_connection.call_count == 3  # noqa: PLR2004
    assert sleep.call_args_list == [call(1.0), call(2.0)]
    connected.__exit__.assert_called_once()


def test_database_readiness_stops_after_finite_attempts(
    readiness_connection: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    readiness_connection.side_effect = psycopg.OperationalError(
        "connection details must not reach logs"
    )
    with patch("time.sleep") as sleep, pytest.raises(SystemExit) as error:
        wait_for_postgres()

    assert error.value.code == 1
    assert readiness_connection.call_count == 6  # noqa: PLR2004
    assert sleep.call_args_list == [call(1), call(2), call(4), call(8), call(16)]
    stderr: str = capsys.readouterr().err
    assert "unavailable after 6 attempts" in stderr
    assert "connection details" not in stderr
