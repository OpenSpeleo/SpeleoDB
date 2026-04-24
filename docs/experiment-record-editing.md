# Experiment Record Editing

## Overview

Station-scoped Scientific Experiments now support editing existing
experiment data records from the private map viewer.

This flow covers `ExperimentRecord` rows attached to a station and an
experiment. It does not change the separate experiment-definition editor
used to manage experiment names, metadata, or field schemas.

## Migration / Behavior Change Notes

The frontend now drives record-action state strictly from the selected
experiment's API flags (`can_write`, `can_delete`), not from the
station's project or surface network. Three observable changes follow:

- A user who previously saw Add / Edit because they had project WRITE
  on the station, but only READ on the experiment, **no longer sees**
  those buttons. The records tab renders an inline "Read-only access"
  banner explaining that experiment-level write access is required.
  Backend behavior is unchanged: those clicks would always have been
  rejected by the inline `SDB_WriteAccess` check on the experiment.
- A user with only project READ on the station but WRITE (or higher) on
  the experiment **now correctly sees** Add / Edit and can use them.
  Both layers (station READ via class-level permission and experiment
  WRITE via the inline check) accept this combination.
- Delete remains admin-only. Writers still see the delete column, but
  the control is disabled unless `can_delete` is true.
- If add/edit/delete returns `403`, the client now re-fetches the
  experiment list and re-renders from the refreshed flags instead of
  mutating the cached experiment object in place.

The authoritative client-side signals are
the experiment-list payload fields `can_write` and `can_delete`
(computed by `ExperimentSerializer`). Any future record-mutation UI must
read those flags directly. Do not
re-introduce project/network-scope heuristics for record mutations.

## Feature Intent

The map viewer already let users:

- list experiment records for a selected station and experiment
- add new records
- delete records (admin only)

Editing completes that workflow so users with write access can correct
measurement values without deleting and recreating rows.

## Engineering Scope

### Frontend

The station experiments UI lives in:

- `frontend_private/static/private/js/map_viewer/stations/experiments.js`
- `frontend_private/static/private/js/map_viewer/api.js`

The frontend uses one shared record workflow for add and edit:

- shared experiment lookup cache (reused for the lifetime of the station
  modal, refreshed on demand and after mutation-time `403`s)
- shared field sorting, parsing, validation, and rendering helpers
- one reusable modal for add and edit (close via `closeRecordModal`)
- in-place table mutation helpers for prepend, update, and remove
- a single module-scoped scroll lock that saves and restores
  `document.body.style.overflow` around modal lifetime, so unrelated
  scroll-lock state is never clobbered

The records table exposes:

- Add / `Edit` when the selected experiment's `can_write` flag is true
- a delete affordance only in writable mode; it is enabled when
  `can_delete` is true and rendered as a disabled admin-only control
  otherwise

The edit modal is prefilled from the selected row and submits a `PUT`
request to the record-detail API. On success, the row is updated in
place without a full reload.

Frontend action visibility is still driven by the selected experiment's
`can_write` / `can_delete` flags. That is sufficient for the
station-scoped map viewer because the caller already had to reach the
station page in the first place. The backend still enforces station
visibility on the record-detail endpoint, so a direct URL cannot mutate
a record from a hidden station even if the caller has experiment-level
permission. When the backend rejects a mutation with `403`, the client
refreshes those experiment flags before re-rendering so stale cached
permissions do not linger.

Module public API (`window.StationExperiments`):

- `render(stationId, container)`
- `openAddRowModal(stationId, experimentId)`
- `openEditRowModal(stationId, experimentId, rowId)`
- `closeRecordModal()` — closes the shared add/edit modal
- `openDeleteRowModal(rowId)` / `closeDeleteRowModal()`
- `confirmDeleteRow(rowId)`

### Backend

The record-detail API lives in:

- `speleodb/api/v2/views/experiment.py`
- `speleodb/api/v2/serializers/experiment.py`

`ExperimentRecordSpecificApiView` accepts `PUT`, `PATCH`, and `DELETE`.

Permission policy (combined as a single `permission_classes` chain):

- `(IsObjectDeletion & SDB_AdminAccess) | (IsObjectEdition & SDB_WriteAccess)`
- effectively: edit (`PUT`/`PATCH`) requires READ visibility on the owning
  station plus WRITE on the experiment; delete requires READ visibility on
  the owning station plus ADMIN on the experiment.
- Object permission resolution traverses `ExperimentRecord -> Station` for
  station visibility and `ExperimentRecord -> Experiment` for the
  write/admin gate (see `speleodb/api/v2/permissions.py`).
- The dual gate is intentionally NOT visible from the view's
  `permission_classes` declaration alone — the station-READ leg is
  enforced inside `BaseAccessLevel.has_object_permission(ExperimentRecord)`.
  The `ExperimentRecordSpecificApiView` class docstring spells this out,
  and the contract is pinned by
  `TestExperimentRecordDetailRequiresStationAccess` (PUT/PATCH/DELETE)
  and `TestExperimentRecordPostDualPermissionContract` (POST) in
  `speleodb/api/v2/tests/test_experiment_records_api.py`.

`ExperimentSerializer` mirrors this contract by exposing:

- `can_write: bool` — true iff the caller has `READ_AND_WRITE` or higher.
- `can_delete: bool` — true iff the caller has `ADMIN`.

Both are computed from `ExperimentUserPermission` for the authenticated
request user. The list view pre-attaches an `experiment_levels_by_id`
context map (single `select_related` query, no N+1). The detail view
falls back to a single `filter().first()`. The frontend reads only these
two booleans for Add / Edit / Delete visibility because station access is
already implied by the page context; the record-detail backend still
checks station visibility independently.

#### Inactive experiments

All record endpoints reject inactive experiments:

- `ExperimentRecordApiView._get_experiment` filters `is_active=True` before
  serving `GET` and `POST` — a direct URL to an inactive experiment returns
  404, not 200/201.
- `ExperimentRecordSpecificApiView.get_queryset` filters
  `experiment__is_active=True` — `PUT`, `PATCH`, and `DELETE` on a record
  whose experiment has been deactivated return 404 rather than silently
  mutating historical data.

This matches the frontend, which filters `is_active=false` out of the
experiment dropdown. Any future "read historical inactive records"
requirement is a deliberate product decision, not a silent backdoor.

#### PUT vs PATCH contract

Both methods validate the final editable JSON `data` payload, but they
build that final state differently:

- `PUT` (full replacement): the request body fully replaces `data`. Any key
  omitted from the payload is removed from the stored record. Use this when
  the client knows the complete intended state — the frontend record-edit
  modal does this.
- `PATCH` (partial merge): the request body is merged into the existing
  `data`. Only keys present in the payload are overwritten; everything else
  is preserved. `PATCH {}` is a no-op on `data`.

In both modes the server rebuilds the serializer payload around server-owned
identity instead of trusting the client:

- `station` and `experiment` stay bound to the existing record.
- `submitter_email` is restored from the existing record (or the current
  user's email if it was historically unset) and cannot be spoofed.

#### Body validation

Non-object bodies (e.g. JSON arrays or strings) are rejected with `400` and a
clear `errors.data` message. The view never coerces a non-dict body into a
dict — that previously hid bugs and could 500 in edge cases.

#### Strict `data` key validation

`ExperimentRecordSerializer.validate` rejects any key in `data` that is not
declared on the target experiment's `experiment_fields`. The mandatory
MEASUREMENT_DATE and SUBMITTER_EMAIL UUIDs are always implicitly declared
via `MandatoryFieldUuid.get_mandatory_fields()`. Unknown keys return `400
{"errors": {"data": ["Unknown field UUID(s): …"]}}` on `POST`/`PUT`/`PATCH`
— no garbage keys can leak into the stored JSON blob.

#### Record value validation

`ExperimentRecordSerializer.validate` walks every field declared on the
target experiment and runs the per-type rules implemented by
`_validate_record_value`. Errors are collected across ALL fields and
the unknown-key check, then raised as a single
`ValidationError({"data": [...messages]})`. The validator never
short-circuits on the first failure — clients see every problem at
once.

Per-type rules:

| Field type | Rules |
|---|---|
| `text` | must be a string |
| `number` | must be `int` or `float`, must NOT be `bool`, must be finite (rejects `NaN`, `+Inf`, `-Inf` via `math.isfinite`) |
| `boolean` | must be a `bool` (string `"true"` is rejected) |
| `date` | must be a string parseable by `parse_date` OR `parse_datetime` (so an ISO datetime like `"2025-01-01T12:30:00"` is accepted on date fields) |
| `select` | must be a string AND must appear in `field_definition["options"]`. Defensive: a malformed definition with no options rejects every value rather than crashing |

Required fields apply to ALL types. A blank or missing required field
fails after `POST`, `PUT`, and merged `PATCH`. The mandatory
MEASUREMENT_DATE / SUBMITTER_EMAIL UUIDs are implicitly required via
`MandatoryFieldUuid.get_mandatory_fields()`.

Note on `NaN` / `Inf`: JSON itself can't represent these, so DRF's
`JSONField` rejects them at parse time before the validator runs. The
`math.isfinite` branch in `_validate_record_value` is the second line
of defense in case the parser layer ever loosens; it is exercised by
a direct unit test of the validator.

## Testing Strategy

### Frontend tests

Coverage lives in:

- `frontend_private/static/private/js/map_viewer/api.test.js`
- `frontend_private/static/private/js/map_viewer/stations/experiments.test.js`

The focused coverage pins:

- experiment-record API helper methods (`PUT`/`POST`/`DELETE` routing)
- add/edit visibility driven by the experiment payload's `can_write` flag
- delete enabled/disabled state driven by the experiment payload's
  `can_delete` flag
- edit modal prefill behavior (text, date, boolean, select)
- successful `PUT` updates in place
- stale async selection responses do not overwrite the current experiment
- record-load failures render an error state instead of the empty-state
  "Add First Record" prompt
- malformed create/update responses are rejected instead of corrupting the
  local rows array
- client-side validation errors (required fields, future dates)
- API error messaging including nested `errors` arrays
- `403` on add/edit/delete re-fetches experiment permissions and re-renders
  the table from the refreshed flags
- add and delete regressions after the refactor
- record modal closes on cancel button, Escape key, and overlay click
- body `overflow` is preserved across the modal lifecycle — closing the
  modal restores whatever value was in effect before the modal opened
  (including `scroll` set by unrelated code)
- boolean field values are submitted as native booleans, not strings
- XSS-safe rendering for experiment metadata, row values, and `data-*`
  attributes (including double-quote escaping)

### Backend tests

Coverage lives in:

- `speleodb/api/v2/tests/test_experiment_records_api.py`
- `speleodb/utils/tests/test_sanitized_serializers.py`

The backend tests pin:

- `PUT` happy path with submitter-email spoof rejection
- `PUT` omitted-field removal (full-replacement semantics)
- `PATCH` merges partial payloads while preserving untouched keys
- `PATCH {}` is a no-op on `data` (regression guard against the historical
  wholesale-replace bug)
- `PATCH` cannot spoof submitter email
- non-dict body returns `400` for `POST`, `PUT`, and `PATCH`
- unknown `data` key UUIDs are rejected with `400` on `POST`/`PUT`/`PATCH`;
  payloads using only mandatory UUIDs succeed
- inactive experiments return `404` on `GET`, `POST`, `PUT`, `PATCH`, and
  `DELETE`
- authentication requirement
- read-only experiment access rejection
- write access allowing edits when station visibility is READ_ONLY
- missing station visibility rejecting direct detail `PUT` / `DELETE`
- admin permission satisfies the OR-of-permissions edit chain
- WRITE-only user is rejected with `403` on `DELETE` (admin-only delete)
- unknown record `404`
- required record fields cannot be omitted on `POST` / `PUT`
- invalid record types and invalid select options are rejected with `400`
- schema-aware sanitization strips HTML from text fields without mangling
  select/date semantics; accented select options survive create/update
- `ExperimentSerializer` exposes `can_write` / `can_delete` accurately for
  READ_ONLY, READ_AND_WRITE, and ADMIN levels, on both the list and detail
  endpoints
- serializer sanitization for edited JSON payloads while preserving
  select strings, numeric values, and boolean values

## Performance Notes

The refactor intentionally avoids new full-table reloads after add, edit,
or delete. The selected experiment rows are still fetched once per
experiment selection, and local row state is mutated in place afterward.
The `403` recovery path refreshes only the experiment metadata flags, not
the full record list.

This keeps the UI responsive and avoids unnecessary duplicate fetches
while also centralizing field logic so future changes do not require
updating multiple modal or table code paths.
