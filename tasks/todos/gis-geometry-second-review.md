# GIS Geometry second adversarial review

Review the complete feature in `ed9de067` against its parent, including every
subsequent correction. The user explicitly requested another full review using
review-agent; proceed through confirmed fixes, full checks, and a follow-up
commit without requesting additional design decisions.

- [x] Independently review backend/authorization, editor/interactions, frontend
      integration, exports, documentation, and the final user requirements.
- [x] Reproduce actionable findings; state severity, location, failure scenario,
      and smallest fix. Review the corrective plan before implementation.
- [x] Implement confirmed fixes with focused regression coverage.
- [x] Run full JavaScript and Python suites serially in the existing container,
      plus relevant PostgreSQL and browser checks. Inspect GitLab audit/cleanup.
- [x] Run all pre-commit hooks, document results, and commit the completed
      review.

Three adversarial reviewers independently own backend, editor, and frontend
integration. The root reviewer owns exports, integration boundaries, final
requirements, and serial verification. Avoid speculative refactors and preserve
the explicit permission-view architecture agreed with the user.

## Root integration review

Rechecked archive selection, eager permission/data snapshots, exact stored
coordinates, revision and creator metadata, filename safety, checksums, omitted
resource handling, and format-version changes. The renamed `layers/` path is
limited to archive layout; original GIS Layer storage keys remain unchanged.
Existing tests cover readable/revoked/inactive geometries and mutation after
snapshot. No new actionable export defect was found.

Rechecked final user requirements against code/docs: Line/Polygon only, shared
30 km² policy and consistency tests, lower fill opacity, random server-palette
creation color, toolbar order, folded panel sizing/chevrons/toggles, and backend
menu order. Confirmed the rejected generic backend modules are absent and GIS
Layer views/serializers are unchanged from the feature's parent.

## Confirmed corrective plan

- P2: A failed initial geometry fetch can overwrite visibility established by a
  newer edit/save. Preserve a newer accepted cached record and the latest user
  visibility when an older request fails; synchronize ordinary failure with
  rendered visibility. Add deferred-response regressions.
- P2: Clipboard completion after closing/reopening the editor accesses detached
  state or updates another draft. Capture the initiating editor session and only
  update that session after asynchronous completion, with success/failure
  regressions for close and reopen.
- P1: After a conflict, restoring the original values leaves conflict recovery
  available but makes the draft appear unchanged. Starting another editor while
  Reload saved is pending can replace its session; the old reload then discards
  the new draft. Reject create/edit entry while the current session is saving or
  reloading, and test this exact conflict-recovery sequence.

These plans preserve existing ownership and revision/session boundaries; no new
state-management abstraction is needed. All three corrections are implemented.

## Verification

The backend reviewer independently traced authorization, malformed inputs,
revision and row-lock behavior, admin/deletion lock order, migrations, contract
loading, and exports. No further backend change was warranted. The first pass's
79 PostgreSQL tests, including three real blocked-writer races, remain
applicable to the unchanged backend.

The editor reviewer demonstrated six failing regressions before correcting the
clipboard and reload races. All 103 focused editor/geometry/camera/interaction
tests passed afterward. The frontend reviewer passed 32 focused layer/panel
tests, including four new delayed-failure cases.

A clean production build emitted `main-D5Q3JdHm.js`. Real Chromium exercised an
actual API revision conflict followed by a delayed reload and a click on Create
Geometry: the original editor remained intact. A delayed clipboard rejection
after opening a later draft left its name/fallback untouched, with no runtime
errors. Temporary browser records, account, and session were removed.

The final full suites passed **1,185 JavaScript tests** and **4,870 Python
tests**, with 181 expected Python skips. GitLab audit
`9080b8c575714ab1961247cc601b2d09` recorded nine creations and ten creation
POSTs, zero violations, no unresolved outcomes, and confirmed deletion marks for
all nine repositories. All execution used the existing application container; no
new test stack was started.

All pre-commit hooks passed after formatting the review notes. This includes
Ruff, mypy, template and JavaScript lint, security/dependency checks, URL
consistency, and a clean production build. No unresolved findings remain from
this pass. The follow-up commit contains all three fixes and their evidence.
