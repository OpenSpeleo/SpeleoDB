#!/usr/bin/env python
"""Provision Kanchi's own database/user on an existing local PostgreSQL server."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

if TYPE_CHECKING:
    from collections.abc import Mapping


MAX_IDENTIFIER_BYTES: int = 63
PROVISIONING_LOCK: str = "speleodb:local-kanchi-database"


class DatabaseSetupError(RuntimeError):
    """Provisioning would modify an unrelated or unsafe existing database role."""


@dataclass(frozen=True)
class ProvisioningResult:
    database_created: bool
    role_created: bool


def _validate_name(value: str) -> None:
    if not value or "\x00" in value or len(value.encode()) > MAX_IDENTIFIER_BYTES:
        raise DatabaseSetupError(
            "Database and role names must fit PostgreSQL identifiers."
        )


def provision_database(
    connection: psycopg.Connection[tuple[Any, ...]],
    *,
    password: str,
    database: str = "kanchi",
    username: str = "kanchi",
) -> ProvisioningResult:
    """Preserve existing data; refuse conflicting ownership before any changes."""
    _validate_name(database)
    _validate_name(username)
    if not password or "\x00" in password:
        raise DatabaseSetupError("A nonempty Kanchi database password is required.")
    if not connection.autocommit:
        raise DatabaseSetupError(
            "Database provisioning requires an autocommit connection."
        )
    if (
        database in {connection.info.dbname, "postgres", "template0", "template1"}
        or username == connection.info.user
        or username.lower().startswith("pg_")
    ):
        raise DatabaseSetupError(
            "Kanchi must use its own database and unprivileged role."
        )
    connection.execute(
        "SELECT pg_advisory_lock(hashtextextended(%s, 0))", (PROVISIONING_LOCK,)
    )
    try:
        return _provision_locked(
            connection, password=password, database=database, username=username
        )
    finally:
        connection.execute(
            "SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (PROVISIONING_LOCK,)
        )


def _provision_locked(
    connection: psycopg.Connection[tuple[Any, ...]],
    *,
    password: str,
    database: str,
    username: str,
) -> ProvisioningResult:
    existing_database: tuple[Any, ...] | None = connection.execute(
        "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s",
        (database,),
    ).fetchone()
    if existing_database is not None and existing_database[0] != username:
        raise DatabaseSetupError("The existing Kanchi database has a different owner.")
    existing_role: tuple[Any, ...] | None = connection.execute(
        "SELECT oid, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, "
        "rolreplication, rolbypassrls FROM pg_roles WHERE rolname = %s",
        (username,),
    ).fetchone()
    if existing_role is not None:
        if not existing_role[1] or any(existing_role[2:]):
            raise DatabaseSetupError("The existing Kanchi role has unsafe privileges.")
        memberships: tuple[Any, ...] | None = connection.execute(
            "SELECT 1 FROM pg_auth_members WHERE roleid = %s OR member = %s LIMIT 1",
            (existing_role[0], existing_role[0]),
        ).fetchone()
        other_database: tuple[Any, ...] | None = connection.execute(
            "SELECT 1 FROM pg_database WHERE datdba = %s AND datname <> %s LIMIT 1",
            (existing_role[0], database),
        ).fetchone()
        if memberships is not None or other_database is not None:
            raise DatabaseSetupError(
                "The existing Kanchi role is shared with other users."
            )
    role: sql.Identifier = sql.Identifier(username)
    database_name: sql.Identifier = sql.Identifier(database)
    if existing_role is None:
        connection.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(role, sql.Literal(password))
        )
    else:
        connection.execute(
            sql.SQL("ALTER ROLE {} PASSWORD {}").format(role, sql.Literal(password))
        )
    if existing_database is None:
        connection.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(database_name, role)
        )
    connection.execute(
        sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(database_name)
    )
    return ProvisioningResult(
        database_created=existing_database is None, role_created=existing_role is None
    )


def administrator_parameters(environment: Mapping[str, str]) -> dict[str, str]:
    return {
        "host": environment.get("POSTGRES_HOST", "localhost"),
        "port": environment.get("POSTGRES_PORT", "5432"),
        "dbname": environment["POSTGRES_DB"],
        "user": environment.get("POSTGRES_USER") or "postgres",
        "password": environment["POSTGRES_PASSWORD"],
        "connect_timeout": "10",
    }


def main() -> int:
    try:
        parameters: dict[str, str] = administrator_parameters(os.environ)
        password: str = os.environ["KANCHI_POSTGRES_PASSWORD"]
        with psycopg.connect(
            make_conninfo(**parameters), autocommit=True
        ) as connection:
            provision_database(
                connection,
                password=password,
                database=os.environ.get("KANCHI_POSTGRES_DB", "kanchi"),
                username=os.environ.get("KANCHI_POSTGRES_USER", "kanchi"),
            )
    except DatabaseSetupError as error:
        print(str(error), file=sys.stderr)  # noqa: T201
        return 1
    except KeyError, psycopg.Error:
        # Database errors can embed the SQL statement containing the password.
        print(  # noqa: T201
            "Kanchi database provisioning failed; check local configuration.",
            file=sys.stderr,
        )
        return 1
    print("Local Kanchi database and dedicated role are ready.")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
