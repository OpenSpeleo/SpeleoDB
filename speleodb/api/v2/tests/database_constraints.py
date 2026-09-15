"""Real, temporary SQL constraints for import rollback integration tests."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from uuid import uuid4

from django.db import connection
from django.db import models

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def unique_import_names(
    model: type[models.Model], *, created_by: str
) -> Iterator[None]:
    """Reject a second imported name through SQLite/PostgreSQL's actual index.

    Scope the constraint to this test's owner and remove it after the request.
    Unlike VARCHAR length enforcement, uniqueness is enforced by both engines.
    """
    constraint: models.UniqueConstraint = models.UniqueConstraint(
        fields=["name"],
        condition=models.Q(created_by=created_by),
        name=f"test_import_name_{uuid4().hex}",
    )
    with connection.schema_editor() as editor:
        editor.add_constraint(model, constraint)
    try:
        yield
    finally:
        with connection.schema_editor() as editor:
            editor.remove_constraint(model, constraint)
