"""Waiting authors must recheck committed content and access under the row lock."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db import connections
from django.db import transaction
from django.http import Http404

from speleodb.gis.geometry_services import GISGeometryConflictError
from speleodb.gis.geometry_services import create_gis_geometry
from speleodb.gis.geometry_services import update_gis_geometry
from speleodb.gis.models import GISGeometry
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from concurrent.futures import Future

LINE: dict[str, Any] = {
    "type": "LineString",
    "coordinates": [[-87.5, 20.1], [-87.499, 20.1]],
}
WAIT_SECONDS = 5


def _wait_for_blocked_writer(writer_pid: int, writer: Future[GISGeometry]) -> None:
    deadline: float = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_backend_pid() = ANY(pg_blocking_pids(%s))", [writer_pid]
            )
            if cursor.fetchone()[0]:
                return
        if writer.done():
            writer.result()
            pytest.fail("The concurrent writer saved without acquiring the row lock.")
        time.sleep(0.01)
    pytest.fail("The concurrent writer did not wait for the geometry transaction.")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("transition", "expected_error"),
    [
        ("edit", GISGeometryConflictError),
        ("revoke", PermissionDenied),
        ("delete", Http404),
    ],
)
def test_queued_author_rechecks_committed_revision_and_access(
    transition: str, expected_error: type[Exception]
) -> None:
    if connection.vendor != "postgresql":
        pytest.skip(
            "Concurrent authoring requires the PostgreSQL integration database."
        )
    creator = UserFactory.create()
    geometry = create_gis_geometry(GISGeometry(name="Original", geojson=LINE), creator)
    backend_pids: Queue[int] = Queue()

    def write_from_another_connection() -> GISGeometry:
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pids.put(cursor.fetchone()[0])
            return update_gis_geometry(
                geometry_id=geometry.id,
                actor=creator,
                expected_revision=1,
                updates={"name": "Queued writer"},
            )
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=1) as executor:
        with transaction.atomic():
            GISGeometry.objects.select_for_update().get(pk=geometry.pk)
            writer = executor.submit(write_from_another_connection)
            _wait_for_blocked_writer(backend_pids.get(timeout=WAIT_SECONDS), writer)
            if transition == "edit":
                update_gis_geometry(
                    geometry_id=geometry.id,
                    actor=creator,
                    expected_revision=1,
                    updates={"name": "Committed writer"},
                )
            elif transition == "revoke":
                geometry.permissions.get(user=creator).deactivate(creator)
            else:
                geometry.deactivate(creator)
        with pytest.raises(expected_error):
            writer.result(timeout=WAIT_SECONDS)

    geometry.refresh_from_db()
    assert geometry.name == ("Committed writer" if transition == "edit" else "Original")
    assert geometry.revision == (2 if transition == "edit" else 1)
    assert geometry.is_active is (transition != "delete")
    assert geometry.permissions.get(user=creator).is_active is (transition == "edit")
