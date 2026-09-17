"""The required-name migration repairs only unnamed historical accounts."""

from __future__ import annotations

from typing import Any

import pytest
from django.db import IntegrityError
from django.db import connection
from django.db import transaction
from django.db.migrations.executor import MigrationExecutor

USERS_0008: list[tuple[str, str]] = [("users", "0008_user_has_api_doc_access")]
USERS_0009: list[tuple[str, str]] = [("users", "0009_require_user_name")]
LEGACY_WHITESPACE: str = (
    "\t\n\v\f\r\x1c\x1d\x1e\x1f \x85\xa0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)


@pytest.mark.django_db(transaction=True)
def test_required_name_migration_repairs_preserves_and_reapplies() -> None:
    executor: MigrationExecutor = MigrationExecutor(connection)
    latest_targets: list[tuple[str, str]] = executor.loader.graph.leaf_nodes()
    invalid_names: tuple[str, ...] = (
        "",
        " \t\n",
        *LEGACY_WHITESPACE,
        LEGACY_WHITESPACE,
    )
    valid_names: tuple[str, ...] = (
        "Ada Lovelace",
        "Élodie D'Arcy",
        "李明",
        "أحمد علي",
        " \tRenée\u3000",
        "... <>",
        "NO NAME",
    )

    try:
        executor.migrate(USERS_0008)
        old_user: type[Any] = executor.loader.project_state(USERS_0008).apps.get_model(
            "users", "User"
        )
        for index, name in enumerate((*invalid_names, *valid_names)):
            old_user.objects.create(
                email=f"historical-{index}@example.com",
                name=name,
                country="FR",
                password="preserve-password-hash",  # noqa: S106
                is_active=index % 2 == 0,
                is_staff=index % 2 != 0,
                has_api_doc_access=True,
            )
        original_rows: list[dict[str, Any]] = list(
            old_user.objects.order_by("id").values()
        )
        expected_rows: list[dict[str, Any]] = [
            {**row, "name": row["name"] if row["name"].strip() else "NO NAME"}
            for row in original_rows
        ]

        executor = MigrationExecutor(connection)
        executor.migrate(USERS_0009)
        migrated_user: type[Any] = executor.loader.project_state(
            USERS_0009
        ).apps.get_model("users", "User")
        assert list(migrated_user.objects.order_by("id").values()) == expected_rows
        with (
            pytest.raises(IntegrityError, match="users_user_name_nonblank"),
            transaction.atomic(),
        ):
            migrated_user.objects.filter(pk=original_rows[0]["id"]).update(name="")

        executor = MigrationExecutor(connection)
        executor.migrate(USERS_0008)
        rolled_back_user: type[Any] = executor.loader.project_state(
            USERS_0008
        ).apps.get_model("users", "User")
        assert list(rolled_back_user.objects.order_by("id").values()) == expected_rows
        rolled_back_user.objects.filter(pk=original_rows[0]["id"]).update(
            name=LEGACY_WHITESPACE
        )

        executor = MigrationExecutor(connection)
        executor.migrate(USERS_0009)
        reapplied_user: type[Any] = executor.loader.project_state(
            USERS_0009
        ).apps.get_model("users", "User")
        assert list(reapplied_user.objects.order_by("id").values()) == expected_rows
        with (
            pytest.raises(IntegrityError, match="users_user_name_nonblank"),
            transaction.atomic(),
        ):
            reapplied_user.objects.filter(pk=original_rows[0]["id"]).update(
                name=LEGACY_WHITESPACE
            )
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(latest_targets)
