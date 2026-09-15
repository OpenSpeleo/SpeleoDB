# Profile and tighten pytest collection

## Plan

- [x] Inventory configured discovery roots, test modules, and collection hooks.
- [x] Profile full collection inside the existing Docker container, separating
      startup/import work, directory traversal, and test generation.
- [x] Apply the smallest measured improvement without removing intended tests.
- [x] Compare collected node IDs and before/after timings inside Docker.
- [x] Document the collection contract, evidence, and remaining costs.

The user authorized profiling and tightening collection. Collection-only runs
must not execute test bodies or recreate the test database. Do not restart
services. Preserve all tracked test roots, including Compose and frontend Django
tests; verify node-ID equality rather than relying only on total counts.

## Review

The baseline spent 31.64 seconds collecting 58,800 `.workdir` directories,
within 36.80 seconds of total collection. No `testpaths` was configured, and
`norecursedirs = ".uv/*"` replaced pytest's normal exclusions.

CLI overrides for the proposed configuration reduced collection to 1.96 seconds.
The final on-disk configuration collected in 1.83 seconds, with the complete
profiled invocation taking 3.73 seconds versus 39.87 seconds before. Directory
collectors dropped from 59,776 to 149; assertions verified no `.workdir`,
`node_modules`, or `.git` directory collectors remained.

Both comparisons retained all 4,619 node IDs in the same order after normalizing
only the five existing random SHA256 parameter IDs. No test bodies ran and no
services restarted. Measurements were sequential after the competing test run
stopped. The initial heavy profile under memory pressure was killed and is not
used as evidence. See
[the collection documentation](../../docs/pytest-collection.md) for the scope,
method, and future profiling commands.

Independent read-only review found no discovery regressions: all 182 tracked
matching test files remain covered, including standalone `tests.py` modules.
Other workspace tasks started adding tests after the measured comparisons;
future totals may increase independently of this configuration change.
