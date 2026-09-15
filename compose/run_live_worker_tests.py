"""Run isolated live-worker tests using the Docker container's PostgreSQL."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote


def main() -> None:
    if not Path("/.dockerenv").exists():
        raise SystemExit("Run this command inside the Docker Compose django container.")
    environment: dict[str, str] = os.environ.copy()
    if not environment.get("TEST_DATABASE_URL"):
        required: tuple[str, ...] = (
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
        )
        missing: list[str] = [key for key in required if not environment.get(key)]
        if missing:
            raise SystemExit(f"Missing container configuration: {', '.join(missing)}")
        user: str = quote(environment["POSTGRES_USER"], safe="")
        password: str = quote(environment["POSTGRES_PASSWORD"], safe="")
        database: str = quote(environment["POSTGRES_DB"], safe="")
        host: str = environment.get("POSTGRES_HOST", "localhost")
        authority: str = f"[{host}]" if ":" in host else host
        port: str = environment.get("POSTGRES_PORT", "5432")
        environment["TEST_DATABASE_URL"] = (
            f"postgresql://{user}:{password}@{authority}:{port}/{database}"
        )
    environment["EXPORTS_LIVE_WORKER_TESTS"] = "1"
    environment.setdefault("TEST_CELERY_BROKER_URL", "redis://localhost:6381/0")
    environment["CELERY_BROKER_URL"] = environment["TEST_CELERY_BROKER_URL"]
    arguments: list[str] = [
        sys.executable,
        "-m",
        "pytest",
        "speleodb/background_jobs/tests/test_live_worker.py",
        *sys.argv[1:],
    ]
    os.execve(sys.executable, arguments, environment)  # noqa: S606


if __name__ == "__main__":
    main()
