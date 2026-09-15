"""Bounded PostgreSQL readiness check shared by the entrypoint and its tests."""

from __future__ import annotations

import os
import sys
import time

import psycopg

MAX_ATTEMPTS: int = 6
CONNECT_TIMEOUT_SECONDS: int = 5
RETRY_BASE_SECONDS: float = 1.0


def wait_for_postgres() -> None:
    for attempt in range(MAX_ATTEMPTS):
        try:
            with psycopg.connect(
                dbname=os.environ["POSTGRES_DB"],
                user=os.environ["POSTGRES_USER"],
                password=os.environ["POSTGRES_PASSWORD"],
                host=os.environ["POSTGRES_HOST"],
                port=os.environ["POSTGRES_PORT"],
                connect_timeout=CONNECT_TIMEOUT_SECONDS,
            ):
                pass
            return
        except psycopg.OperationalError:
            if attempt + 1 == MAX_ATTEMPTS:
                sys.stderr.write(
                    f"PostgreSQL is unavailable after {MAX_ATTEMPTS} attempts.\n"
                )
                raise SystemExit(1) from None
            delay: float = RETRY_BASE_SECONDS * (2**attempt)
            sys.stderr.write(
                f"Waiting for PostgreSQL: attempt {attempt + 1}/{MAX_ATTEMPTS} "
                f"failed; retrying in {delay:g}s.\n"
            )
            time.sleep(delay)


if __name__ == "__main__":
    wait_for_postgres()
