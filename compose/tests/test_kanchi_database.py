"""Exercise provisioning against isolated databases/roles on real local PostgreSQL."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from compose.setup_kanchi_database import DatabaseSetupError
from compose.setup_kanchi_database import administrator_parameters
from compose.setup_kanchi_database import provision_database

if TYPE_CHECKING:
    from collections.abc import Generator


SCRIPT: Path = Path(__file__).parents[1] / "setup_kanchi_database.py"


@dataclass
class IsolatedDatabase:
    connection: psycopg.Connection[tuple[Any, ...]]
    parameters: dict[str, str]
    database: str
    username: str
    password: str

    def provision(self, *, password: str | None = None) -> None:
        provision_database(
            self.connection,
            database=self.database,
            username=self.username,
            password=password if password is not None else self.password,
        )

    def connect(
        self, *, password: str | None = None
    ) -> psycopg.Connection[tuple[Any, ...]]:
        return psycopg.connect(
            make_conninfo(
                **(
                    self.parameters
                    | {
                        "dbname": self.database,
                        "user": self.username,
                        "password": password if password is not None else self.password,
                    }
                )
            ),
            autocommit=True,
        )


@pytest.fixture
def isolated_database() -> Generator[IsolatedDatabase]:
    parameters: dict[str, str] = administrator_parameters(os.environ)
    assert parameters["host"] in {"localhost", "127.0.0.1", "postgres"}
    identifier: str = uuid.uuid4().hex
    with psycopg.connect(make_conninfo(**parameters), autocommit=True) as connection:
        fixture = IsolatedDatabase(
            connection=connection,
            parameters=parameters,
            database=f"kanchi_test_db_{identifier}",
            username=f"kanchi_test_role_{identifier}",
            password=f"quoted-'\\-password-{uuid.uuid4().hex}",
        )
        try:
            yield fixture
        finally:
            assert fixture.database.startswith("kanchi_test_db_")
            assert fixture.username.startswith("kanchi_test_role_")
            connection.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(fixture.database)
                )
            )
            connection.execute(
                sql.SQL("DROP ROLE IF EXISTS {}").format(
                    sql.Identifier(fixture.username)
                )
            )


def test_provisioned_role_owns_private_database_and_can_create_tables(
    isolated_database: IsolatedDatabase,
) -> None:
    fixture: IsolatedDatabase = isolated_database
    result = provision_database(
        fixture.connection,
        database=fixture.database,
        username=fixture.username,
        password=fixture.password,
    )
    assert result.database_created
    assert result.role_created
    owner: tuple[Any, ...] | None = fixture.connection.execute(
        "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s",
        (fixture.database,),
    ).fetchone()
    assert owner == (fixture.username,)
    public_access: tuple[Any, ...] | None = fixture.connection.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_database, aclexplode(datacl) AS acl "
        "WHERE datname = %s AND acl.grantee = 0)",
        (fixture.database,),
    ).fetchone()
    assert public_access == (False,)
    with fixture.connect() as connection:
        connection.execute("CREATE TABLE kanchi_history (task_id text PRIMARY KEY)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                sql.SQL("ALTER ROLE {} CREATEDB").format(
                    sql.Identifier(fixture.username)
                )
            )


def test_repeated_setup_preserves_history_and_rotates_only_its_password(
    isolated_database: IsolatedDatabase,
) -> None:
    fixture: IsolatedDatabase = isolated_database
    fixture.provision()
    with fixture.connect() as connection:
        connection.execute("CREATE TABLE kanchi_history (task_id text PRIMARY KEY)")
        connection.execute("INSERT INTO kanchi_history VALUES ('preserved-task')")
    replacement: str = uuid.uuid4().hex
    result = provision_database(
        fixture.connection,
        database=fixture.database,
        username=fixture.username,
        password=replacement,
    )
    assert not result.database_created
    assert not result.role_created
    with fixture.connect(password=replacement) as connection:
        assert connection.execute("SELECT task_id FROM kanchi_history").fetchone() == (
            "preserved-task",
        )
    with pytest.raises(psycopg.OperationalError):
        fixture.connect().close()


def test_existing_database_with_different_owner_is_untouched(
    isolated_database: IsolatedDatabase,
) -> None:
    fixture: IsolatedDatabase = isolated_database
    fixture.connection.execute(
        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(fixture.database))
    )
    with pytest.raises(DatabaseSetupError, match="different owner"):
        fixture.provision()
    assert (
        fixture.connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (fixture.username,)
        ).fetchone()
        is None
    )
    assert fixture.connection.execute(
        "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s",
        (fixture.database,),
    ).fetchone() == (fixture.parameters["user"],)


@pytest.mark.parametrize(
    "attribute", ["SUPERUSER", "CREATEDB", "CREATEROLE", "REPLICATION", "BYPASSRLS"]
)
def test_unsafe_existing_role_is_rejected(
    isolated_database: IsolatedDatabase, attribute: str
) -> None:
    fixture: IsolatedDatabase = isolated_database
    fixture.connection.execute(
        sql.SQL("CREATE ROLE {} LOGIN {}").format(
            sql.Identifier(fixture.username), sql.SQL(attribute)
        )
    )
    with pytest.raises(DatabaseSetupError, match="unsafe privileges"):
        fixture.provision()
    assert (
        fixture.connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (fixture.database,)
        ).fetchone()
        is None
    )


def test_existing_role_membership_is_rejected(
    isolated_database: IsolatedDatabase,
) -> None:
    fixture: IsolatedDatabase = isolated_database
    role: sql.Identifier = sql.Identifier(fixture.username)
    fixture.connection.execute(sql.SQL("CREATE ROLE {} LOGIN").format(role))
    fixture.connection.execute(sql.SQL("GRANT pg_read_all_data TO {}").format(role))
    with pytest.raises(DatabaseSetupError, match="shared with other users"):
        fixture.provision()


def test_database_and_role_identifiers_are_safely_quoted(
    isolated_database: IsolatedDatabase,
) -> None:
    fixture: IsolatedDatabase = isolated_database
    fixture.database += '";x'
    fixture.username += '";x'
    fixture.provision()
    with fixture.connect() as connection:
        assert connection.execute(
            "SELECT current_database(), current_user"
        ).fetchone() == (
            fixture.database,
            fixture.username,
        )


def test_cli_uses_environment_without_printing_passwords(
    isolated_database: IsolatedDatabase,
) -> None:
    fixture: IsolatedDatabase = isolated_database
    environment: dict[str, str] = os.environ | {
        "KANCHI_POSTGRES_DB": fixture.database,
        "KANCHI_POSTGRES_USER": fixture.username,
        "KANCHI_POSTGRES_PASSWORD": fixture.password,
    }
    for _ in range(2):
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(SCRIPT)],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert fixture.password not in result.stdout + result.stderr
    with fixture.connect() as connection:
        assert connection.execute("SELECT current_user").fetchone() == (
            fixture.username,
        )
