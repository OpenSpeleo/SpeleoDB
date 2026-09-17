# GIS Geometry adversarial review

- [x] Review the entire change against HEAD: backend/permissions/validation,
      editor/interactions/camera, frontend integration/management, and exports.
- [x] For each actionable defect, record severity, location, concrete failure,
      and smallest fix; review/refine the corrective plan and implement it.
- [x] Verify corrections with targeted regressions and relevant browser checks.
- [x] Run full Python and JavaScript suites serially where shared services
      require it, inside the existing application container; inspect GitLab
      audit/cleanup.
- [x] Run `prek run -a`, resolve all failures, and check migrations/build
      output.
- [x] Document final evidence and commit all completed changes.

The user explicitly authorized proceeding through corrections, full checks, and
commit via the review-agent skill. Review includes every staged and unstaged
feature file and all subsequent refinements. Three adversarial reviewers own
backend, editor, and frontend integration; the primary agent reviews exports,
coordinates fixes, and owns final serial verification and commit.

## Findings and corrections

- **P2 — Editor gesture boundaries:** in `geometry_editor/editor.js`, a drag
  without a generated click swallowed the next deliberate click; an unfinished
  drag could overwrite Undo; a second touch could move a vertex during a pinch.
  Reset suppression on a new gesture, finish drags before draft commands, and
  cancel vertex dragging when a multi-touch map gesture starts.
- **P2 — Keyboard and GPS editing:** the same editor intercepted native Enter
  activation, disabled GPS updates at the vertex cap, and lost focus when
  rebuilding vertex controls. Preserve native control activation, limit only
  additions, and restore focus to replacement controls.
- **P2 — Metadata races:** `config.js` cleared locally saved records after a
  failed retry and could overwrite newer local state with a delayed response.
  Preserve changed records using the request-start revision snapshot and the
  existing revision-aware upsert, while still removing unchanged revoked rows.
- **P2 — Panel and editor focus:** panel refresh/collapse removed or hid the
  focused control; direct-link editor opening captured `document.body`, which
  cannot restore useful focus. Preserve focus through panel transitions and
  verify successful editor focus restoration before accepting a target.
- **P2 — Incomplete concurrency verification:** new real PostgreSQL tests prove
  queued writers cannot bypass revision conflicts, revocation, or deletion.
  Existing production locking passed; no speculative locking changes were made.
- **P2 — Stale toolbar assertion:** the backend template test still expected
  Import GPS before Create Geometry. Updated it to the user's final order.
- **Maintainability — GIS-only permission abstraction:** removed
  `direct_gis_permissions.py` and the corresponding serializer base. Geometry
  uses explicit typed endpoints consistent with existing entities; GIS Layer's
  view and serializer are restored exactly. Shared validation remains reused.

The corrective plan was refined to fix existing gesture, cache, and focus
boundaries without adding a second state-management or permission framework.
Backend validation, exports, and camera fitting had no further actionable
runtime findings. Detailed evidence lives in the backend, editor, and frontend
review task documents.

## Verification

- The final full Python suite passed **4,870 tests**, with 181 skips. The three
  PostgreSQL-only race tests skipped by SQLite passed in the dedicated run.
  GitLab audit `0f3060ff319f4025ada87a7b09da0bbf` recorded **nine creations and
  ten creation POSTs**, zero violations, no unresolved outcomes, and confirmed
  deletion marks for all nine repositories.
- All **1,174 JavaScript tests** across 72 files passed in the running
  container.
- The final permission rewrite passed **79 PostgreSQL tests and three
  subtests**, including the three blocked-writer races. Audit
  `3e7d11b6018d4fdaa082cb50b868819c`: zero repository creations, creation POSTs,
  violations, or unresolved outcomes.
- A clean Vite build passed. Real Chromium loaded its emitted `main-Dfu7-JQK.js`
  chunk from Django and passed native Enter/GPS/save, asynchronous toggle focus,
  direct-link editor close focus, GPS updates at 100 vertices, and mobile
  disclosure/close checks with no runtime errors. Temporary QA records, user,
  and session were removed.
- An initial overlapping verification run hit timeout-only failures in two
  JavaScript tests, the development-reloader subprocess, and a GitLab lookup.
  The standalone JavaScript rerun passed without changing tests or timeouts. The
  full Python rerun also passed unchanged, including both affected
  infrastructure tests. Final verification ran serially to avoid this resource
  contention.
- All pre-commit hooks passed after Markdown formatting, including Ruff, mypy,
  security/dependency checks, template checks, JavaScript lint, URL consistency,
  and the clean Vite build. Both migrations are applied locally and migration
  drift is clean. All completed feature and review changes are included in the
  final commit; no push was requested.
