"""Readiness uses a real isolated-test-database connection."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest
from django.db import connection

from compose.wait_for_postgres import wait_for_postgres


@pytest.fixture
def readiness_connections(
    monkeypatch: pytest.MonkeyPatch,
) -> list[psycopg.Connection[Any]]:
    # pytest-django has selected its isolated database before fixture setup.
    database = connection.settings_dict
    assert str(database["NAME"]).startswith("test_"), "Require pytest's test database"
    for name, value in {
        "POSTGRES_DB": database["NAME"],
        "POSTGRES_USER": database["USER"],
        "POSTGRES_PASSWORD": database["PASSWORD"],
        "POSTGRES_HOST": database["HOST"],
        "POSTGRES_PORT": database["PORT"] or 5432,
    }.items():
        monkeypatch.setenv(name, str(value))
    opened: list[psycopg.Connection[Any]] = []
    real_connect = psycopg.connect

    def connect(**kwargs: Any) -> psycopg.Connection[Any]:
        result = real_connect(**kwargs)
        opened.append(result)
        return result

    monkeypatch.setattr(psycopg, "connect", connect)
    return opened


@pytest.mark.django_db
def test_database_readiness_closes_actual_connection(
    readiness_connections: list[psycopg.Connection[Any]],
) -> None:
    wait_for_postgres()
    assert len(readiness_connections) == 1
    assert readiness_connections[0].closed
