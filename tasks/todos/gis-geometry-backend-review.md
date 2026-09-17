# GIS Geometry backend adversarial review

- [x] Review models, migrations, validation, services, serializers, API access,
      sharing, admin, and compatibility with GIS Layer.
- [x] Refine the corrective plan: preserve the existing locking implementation;
      add real overlapping PostgreSQL transaction coverage before changing it.
- [x] Prove a queued writer cannot overwrite a concurrently committed revision.
- [x] Prove a queued writer cannot save after its permission is revoked or the
      geometry is deleted.
- [x] Run focused SQLite and PostgreSQL tests in the running container, then
      return results for the root agent's full-suite and pre-commit
      verification.

The concrete gap is concurrency verification: existing tests check stale edits
sequentially or look for `FOR UPDATE` in SQL, which cannot establish what a
waiting editor sees after another transaction commits. The new regression will
use two real database connections and observe PostgreSQL's blocking PID state;
it will not substitute ORM behavior or rely on a sleep to order the writes.

## Findings and verification

- **P2 — Stale toolbar order regression test:**
  `frontend_private/tests/test_gis_geometry_views.py` still required Import GPS
  before Create Geometry, contrary to the user's final order and the actual
  template. A full Python run therefore failed. Updated the assertion to the
  approved order without changing correct application behavior.
- **P2 — Missing concurrent-write evidence:**
  `speleodb/gis/tests/test_gis_geometry.py` only exercised sequential stale
  saves. Added `test_gis_geometry_concurrency.py` to prove that a queued author
  cannot overwrite a concurrent save or save after committed
  revocation/deletion. The existing production locks passed all three races; no
  runtime change was justified.

The initial SQLite focused run passed 75 tests and three subtests, skipped the
three PostgreSQL concurrency cases, and exposed the stale toolbar assertion.
After correcting it, PostgreSQL passed all 79 tests and three subtests. Ruff
passed. The root review owns the final full SQLite run and all pre-commit
checks. Both focused GitLab audits recorded zero creations, zero creation POSTs,
and zero violations; PostgreSQL audit: `7d12f5fa6e584c75be9678ecfddc1831`.

## Permission architecture correction

- [x] Review the user's objection to a GIS-only generic permission view against
      established GPS Track and GIS Layer patterns.
- [x] Remove the new generic GIS permission view and restore the existing typed
      GIS Layer implementation.
- [x] Implement Geometry sharing explicitly beside its collection/detail views,
      retaining row locks, atomic mutations, and response contracts.
- [x] Remove the analogous GIS-only serializer abstraction; preserve concrete,
      typed serializer methods consistent with GPS Track and GIS Layer.
- [x] Retain the established shared request parser and document the
      architecture.
- [x] Validate lint and return the implementation for serial full-suite tests.

The refined plan keeps entity-specific querysets, serializer types, and
transaction boundaries visible. A generic layer serving only two of the many
directly shared models adds indirection without establishing a consistent
abstraction. This correction does not expand into a repository-wide rewrite.

Removed both new GIS-only base modules. GIS Layer's permission view and
serializer are restored exactly to their pre-feature implementations. Geometry
now keeps its concrete permission view beside the collection/detail endpoints
and its typed capability methods in its own serializer. Response bodies, error
statuses, atomic mutation scopes, geometry row locks, and access rechecks are
preserved. Ruff and focused mypy passed; the root review will rerun final tests
after the ongoing baseline suite releases the shared test database.
