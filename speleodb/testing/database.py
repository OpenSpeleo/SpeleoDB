"""Share pytest's isolated PostgreSQL database with real child processes."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote
from urllib.parse import urlencode

from django.db import connection


def postgres_test_database_url() -> str:
    database: dict[str, Any] = connection.settings_dict
    assert connection.vendor == "postgresql", "Live processes require PostgreSQL."
    assert str(database["NAME"]).startswith("test_"), (
        "Refusing to run a child process against a database without the test_ prefix."
    )
    host: str = str(database.get("HOST") or "localhost")
    assert not host.startswith("/"), "Use a TCP PostgreSQL address for live tests."
    authority: str = f"[{host}]" if ":" in host else host
    user: str = quote(str(database.get("USER") or ""), safe="")
    password: str = quote(str(database.get("PASSWORD") or ""), safe="")
    name: str = quote(str(database["NAME"]), safe="")
    port: str = str(database.get("PORT") or "5432")
    options: dict[str, str] = {
        key: str(value)
        for key, value in database.get("OPTIONS", {}).items()
        if key in {"sslmode", "sslrootcert", "sslcert", "sslkey", "options"}
    }
    query: str = f"?{urlencode(options)}" if options else ""
    return f"postgresql://{user}:{password}@{authority}:{port}/{name}{query}"
