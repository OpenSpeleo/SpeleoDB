# Exploration leads from survey shot comments

The latest survey revision can create exploration leads while its GeoJSON is
generated. Ariane, Compass and Stalagmight use their existing loop-closure
presets. Leads are attached to the SpeleoDB project, independently of individual
Git commits and generated map artifacts.

## Directions and user ownership

Complete comment tokens such as `!N!`, `!NNW!` and `!125!` describe clockwise
bearings from geographic north. All sixteen cardinal directions, including east,
are accepted by searching an uppercased copy of the entire comment. Numeric
tokens are integer degrees from zero inclusive to one full turn exclusive.
Invalid tokens are silently ignored. Equivalent directions are deduplicated, and
the first three distinct valid directions are retained in source order. More
directions do not create another lead.

Creation copies the entire native shot comment into `description`, preserving
its whitespace and text. The creating identity is the source commit author's
email, with the project creator as fallback. Comments are displayed as escaped
plain text. The normal description-editing API retains its sanitization policy;
heading-only edits omit unchanged descriptions.

`directions` contains one to three complete entries with `heading` and `checked`
keys. Each heading is a finite bearing in `[0, 360)` or `null`; each checked
state is a JSON boolean. Duplicate bearings are allowed and remain independent.
An undirected lead is represented by `[{"heading": null, "checked": false}]` and
can be checked without setting a bearing. Newly imported entries start
unchecked.

JSON requests send the structured array directly. Multipart and URL-encoded
requests send the same array as a JSON-encoded string. PATCH omission preserves
the existing entries; a supplied nonempty array replaces them atomically. A
nullable bearing clears only that bearing, preserving its checked state. Entry
removal removes its state with it; the retained entries stay together. Model/API
validation and PostgreSQL constraints enforce the required entry structure,
boolean states, bearing bounds and list size. Existing update permissions apply
to checking, with no separate mutation endpoint.

`is_fully_checked` is read-only and derived from the entries in both the API and
lead GeoJSON. It is true only when every entry is checked. Clients cannot write
an aggregate state independently of its directions. Status-only edits omit an
unchanged description, retaining the exact original survey comment.

### Direction-state data preservation

The direction-state data migration converts saved numeric headings into
unchecked entries, retaining order, duplicates and fractional bearings. Empty
heading arrays become one undirected unchecked entry. The SQL backfill preserves
parent IDs, descriptions, coordinates, creator, timestamps and source records.
Reversing the migration restores numeric bearings in order but necessarily loses
checked states and undirected entries, which the earlier schema cannot
represent. Clients use `directions`; numeric `headings` is not a supported API
field.

### Imported lead ownership

After creation, survey processing never updates an existing lead row. Its
description, directions and checked states, coordinates, creator and timestamps
remain unchanged, including when a user has moved the lead or reset every
direction. Changed measurements, anchors, comments and solved coordinates do not
move an existing lead. Checked states and edited lead bearings never participate
in source matching. A recognized source may add identity aliases without
changing its lead; a source that disappears leaves its existing lead in place.

## Exactly what counts as an existing source

**Every lookup is restricted to the same SpeleoDB project.** Identical
signatures in another project cannot suppress creation or claim a lead. Manual
leads have no source records and remain independent, even at identical
coordinates.

`ExplorationLeadSource` stores one signature per row, with a canonical JSON
payload, its SHA-256 digest, signature kind, project and nullable lead
reference. The unique index covers project, kind and digest. Full payloads
remain available to inspect identity decisions and detect an unexpected digest
collision.

Signatures are evaluated in this order:

1. Native UUID, normalized to its canonical string. **The UUID payload has no
   format, file, survey or section prefix.**
2. Native shot ID and native From ID.
3. Native shot ID, measured length in metres and native measured azimuth.

The third signature uses the survey measurement, never a lead direction parsed
from the comment. Finite measurements have deterministic decimal serialization;
azimuth is normalized to one turn. Missing measurements omit this signature.
There is no fuzzy coordinate or measurement tolerance.

Only the non-UUID signatures include source format and a native namespace:

| Format      | Shot ID                   | From ID                                                     | Additional namespace                      |
| ----------- | ------------------------- | ----------------------------------------------------------- | ----------------------------------------- |
| Ariane      | Native `ID`               | Native `FromID`                                             | None                                      |
| Compass     | Raw TO station name       | Raw FROM station name                                       | Project-relative DAT path and survey name |
| Stalagmight | Native SQLite shot row ID | Native predecessor row ID, or a typed section-root identity | None                                      |

Stalagmight explicit graph parents are resolved through native permanent numbers
back to row IDs. This preserves identity across supported schema changes that
retain those rows. Adapter-generated observation indices are not identifiers.
Compass has no native shot UUID. Its rendered feature UUID is not used.
Conversion-generated UUIDs, traversal order, commit SHA, coordinates, comments,
lead directions and temporary filenames never participate in a signature.

A match at the highest available priority selects the existing lead. Lower
priorities cannot select a different winner. Current observations that propose
different destinations for the same lead at equal priority do not learn new
aliases and produce a warning. There is no merge or existing-lead update.
Ordinary matching and malformed comment tokens are silent.

Each conversion resolves its whole observation batch before writing. Persisted
signature owners remain fixed throughout that resolution. Unclaimed aliases
connect current observations in priority order without overriding a known UUID
owner. Disputed new aliases remain unclaimed. Brand-new observations connected
by shared signatures must agree on one destination before a lead is created;
otherwise the ambiguous group is skipped. These decisions do not depend on
export traversal order.

Successful matching retains all old signatures and adds newly observed,
unclaimed signatures. A signature already owned by another lead is never
reassigned. Keeping old signatures allows a newly learned UUID to connect a
later edit even after other native identifiers change.

These rules are exact, reproducible heuristics. If every available signature
changes, continuity cannot be inferred. Renaming a Compass DAT file or survey
changes its namespace. Reusing non-UUID identities can create a false match.
Hashing makes lookup efficient; it cannot recover identity missing from source
data. Do not replace these rules with positional or nearest-point matching.

## Deletion and history retention

Deleting a lead retains its source records with a null lead reference. Such a
record is a tombstone. Any tombstone match suppresses creation and live alias
learning, including when another signature matches a live lead. Newly observed
unclaimed signatures are retained as tombstones as well.

Deletion evidence propagates through connected current aliases before live
matching or creation. This prevents an earlier observation in the same batch
from claiming a new signature that a later observation connects to a tombstone.

Tombstones and live source records survive GeoJSON replacement, artifact purge
and Git-history metadata reset. They have no foreign key to a commit or
artifact. Deleting the owning project removes its leads and source records.
There is no automatic tombstone expiry or lead recreation command.

## Conversion and atomic publication

`Project.build_geojson()` returns `GeoJSONBuildResult`, containing ordinary
GeoJSON and a tuple of `ResolvedSurveyShot` observations. The exporters'
optional `on_resolved_shot` callbacks supply native provenance and the original
TO endpoint's final coordinates from the same numerical solve. Compass and
Stalagmight may reverse traversal; the rendered line's last point is therefore
not a reliable substitute. Compass observations are retained independently of
rendered-leg deduplication. Synthetic, excluded and unresolved observations do
not import leads.

Source metadata stays outside published survey GeoJSON and source files.
Stalagmight provenance survives the immutable closure snapshot without appearing
in ordinary exported survey JSON.

`Project.sync_exploration_leads()` owns matching and persistence. It checks
fresh project-scoped history, bypassing prefetched history. Recorded descendants
supersede their ancestors even when Git timestamps tie or run backwards; the
application's canonical ordering resolves unrelated recorded tips. This import
rule does not change the API's history ordering.

History conversion registers the complete ancestry before publishing artifacts
and passes source observations only for the repository's HEAD. Historical
revisions, including forced rebuilds and older queued tasks, cannot create leads
or learn aliases. An unusable latest revision does not authorize importing an
older usable revision, including when history metadata has been cleared.

Artifact publication uploads the object first, then synchronizes leads inside
the existing database transaction that replaces the artifact row. Failure rolls
back artifact, lead and signature changes and invokes the established
unpublished object cleanup. Earlier artifacts remain available. Unexpected
failures retain their traceback and fail the existing task; invalid markers and
expected conversion omissions do not become task failures.

Signature lookups and writes are batched. The freshness guard reads project
parent IDs once per nonempty import batch, not once per shot. Matching does not
add a solver pass, per-shot database queries, new scheduler, queue or
project-operation lock.

Existing artifacts retain their normal skip behavior. Operators can use the
existing explicit force-recompute operation to import current annotations for
existing projects. History rebuilds only synchronize the latest revision.

## Web, mobile and shared package ownership

`@speleodb/map-core` owns structured direction validation, completion rules and
geographic cone geometry. `@speleodb/map-viewer` owns marker/cone styling,
completion filters and the editable/read-only DOM compass. Web and mobile own
modal state, permissions, storage and map lifecycle integration.

The compact compass supports up to three directions. Its shaded face has fine
15-degree ticks, a highlighted north marker and a two-tone red needle. A slim
Lead 1, Lead 2 and Lead 3 tab strip below the compass selects the direction
shown by a single active needle. One persistent bearing field sits in the
compass center for precise numeric editing. Its centered text uses a
three-character field and whole degrees. Existing fractional bearings are
rounded for display without changing their stored values; new edits through the
compass use whole degrees. Prominent plus and minus controls add a heading and
remove the selected entry; removing the last heading unsets its direction while
preserving its checked state. Setting that undirected lead's heading again also
preserves status. An additional entry starts unchecked. There is no Reset All
action. Switching tabs preserves the mounted dial and editor and all direction
values. Pointer/touch adjustment and keyboard editing remain available. Changes
remain drafts until saved; cancellation discards them and failed saves preserve
them. Read-only web users and mobile users retain tab navigation without edit
controls. Saved directions do not subscribe to device-heading sensors.

Web lead dialogs retain their original presentation: the details panel is first
and always expanded, the description is underneath, and the compass follows the
description under a small Directions heading matching the other section labels.
The compass has a -20px top margin, intentionally overlapping the heading's row.
Description fields start at two lines high and remain vertically resizable.
Coordinates and creation metadata remain visible in the existing details panel.
The editable details footer divides the available width equally between its
action buttons, with 12px gaps. The shared modal's normal presentation is
unchanged.

Each unchecked entry with a heading creates a fifteen-metre geographic sector
with a forty-five-degree opening, red fill at eighty-percent opacity, above the
lead marker. The cone shares its marker's zoom threshold
(`MAP_LAYER_MIN_ZOOM.EXPLORATION_LEAD_SYMBOL`, set to 15 in
`@speleodb/map-viewer` for both web and mobile) and project/category/country
visibility. Both marker variants consume that constant and the cone builder
applies it directly. It has no minimum pixel enlargement and is naturally small
at overview zooms. Geometry updates when coordinates, headings or checked states
change, including drag rollback, and is restored with the existing style
lifecycle.

A compact single-row panel beneath the selector shows the selected lead and its
Checked or Unchecked status. A direct Mark checked or Mark unchecked button
changes that entry. When multiple entries exist, compact Check all and Uncheck
all buttons sit above the compass, aligned to the right and outside the panel.
They fit their labels, with solid slate fills, visible borders and bright
semibold text. Disabled actions remain muted. There is no checkbox or separate
progress footer, and the lead tabs keep their normal geometry. Checked tabs use
muted green text with a fine bottom accent, separate from the filled selection
treatment.

Both bulk actions are directly available; an action is disabled when every entry
already has that status. Native buttons follow the dialog's normal keyboard
navigation. Changes remain drafts for the open ExplorationLead, saved with Save
Changes; descriptions are omitted when unchanged. Read-only users can select
every bearing in the same compass. Bulk actions and the bottom status panel are
omitted; checked state remains visible on the tabs.

The Checked Exploration Leads display preference defaults off and is local to
each app. When every entry is checked, the marker is hidden unless that
preference is on; then it uses green artwork at 75% opacity, with no cones.
Partially checked leads retain their normal marker and only unchecked bearings
produce cones. The marker's circle fallback follows the same color/opacity rule,
including its outline. Shared code derives green artwork from the bundled normal
raster while retaining the white symbol and alpha, without another asset
request.

Category, country and project gates still apply. Disabling the Exploration leads
category retains the subordinate preference; reset restores it off. The setting
is a muted, smaller row indented beneath its parent, without a card or badge.
Its tooltip and accessible description explain the parent gate when disabled.
Web settings switches keep the native checkbox as the pointer target; decorative
sliders do not intercept clicks, including in the completion/reopening workflow.
Filtering retains all records and does not refetch or regenerate cone geometry.
Hidden markers are excluded from hit testing. Shared filters are reapplied when
project visibility or map style changes, preventing completed leads from
reappearing unexpectedly.

Mobile caches all direction/status entries in its existing overlay GeoJSON. Its
local migration converts cached numeric headings into unchecked entries,
preserving cache timestamps and unrelated downloads. Empty or older unset data
becomes one undirected unchecked entry. A successful normal overlay sync
refreshes statuses independently of survey commits; failures retain the last
successful offline snapshot. The setting works offline. Mobile has no checked
state mutation controls or writes. Public web viewers retain their existing
policy and do not gain lead access.

## Verification

Backend regressions cover parsing, real constraints and persistence, signature
priority/history, project isolation, deletion, latest-only changes and atomic
publication. Small native source fixtures exercise reverse traversal and solved
destinations. Frontend tests cover requests, draft state, visibility, movement,
offline data and shared geometry; browser tests cover native compass interaction
and hiding, revealing and reopening completed leads.

### Native-file regression pipeline

`speleodb/gis/tests/test_exploration_lead_pipeline.py` reads and edits copies of
the checked-in Ariane `test_simple.tml` and Compass `sample.mak`/DAT fixtures.
TML stays a real ZIP containing `Data.xml`, with separate cases retaining native
UUIDs or omitting them entirely. Stalagmight uses the small native SQLite
fixture in `speleodb/testing/stalagmight.py`, including a hidden jump, merged
sections, an anchor and azimuth/depth corrections. Files and uncompressed XML
stay within the repository's test fixture size limit. No developer survey is
modified.

Each case uses a real local Git repository, immutable source materialization,
the installed readers and loop-closure solvers, artifact publication to the
configured test object store, and the isolated PostgreSQL test database. The
fixture removes only its own project's storage prefix. It provisions no GitLab
repositories and does not replace parsers, matching, publication or ORM calls.

| Boundary                  | Regression coverage                                                                                                                                                              |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Initial import            | Lowercase markers; complete original comment; correct native TO location; invalid tokens ignored                                                                                 |
| User ownership            | Every persisted lead field, including partial/full checked states, undirected checked leads, edited coordinates and modification time, survives recomputation and future commits |
| Slight shot corrections   | Small length and azimuth changes plus a different comment retain the same lead ID via native endpoints; the existing lead row remains unchanged                                  |
| UUID changes              | A changed native UUID and measurement retain the same lead and learn the new UUID; a subsequent native ID change still matches without replacing user content                    |
| Deletion                  | Changed measurements, comments and UUIDs cannot resurrect a deleted lead; tombstones survive artifact removal and metadata reconstruction                                        |
| Existing artifacts        | Ordinary recomputation skips them; forced recomputation parses comments and imports only the newest revision                                                                     |
| History failures          | Missing or invalid HEAD sources cannot import historical annotations when metadata is absent; unexpected conversion failures remain failures                                     |
| Tied or backdated commits | Reconstructed history, including partially retained metadata, respects parent/child relationships rather than timestamps or metadata insertion order                             |

`test_exploration_lead_headings.py` covers complete direction writes across all
supported request encodings, every checked-state combination for one through
three entries, duplicate bearings, undirected state, omission, partial removal,
invalid-write preservation and REST/GeoJSON agreement. The API permission matrix
also performs checked-state writes.
`test_exploration_lead_directions_migration.py` executes the actual migration in
both directions, preserving historical rows and source tombstones and restoring
the latest schema afterward.

`test_exploration_lead_import.py` retains the smaller matching matrix: project
isolation, manual leads, UUID normalization and priority, unavailable or wrapped
measurements, learned aliases, contradictory destinations, tombstone propagation
and batch-order independence. These tests deliberately use resolved observations
to isolate ambiguity rules; they complement the real-file pipeline. Publication
rollback and real worker execution remain in
`test_project_geojson_replacement.py` and `test_geojson_generation.py`.

`test_exploration_lead_native_edges.py` publishes additional small native files:
reversed and duplicated Compass observations with excluded shots and changed
file/survey namespaces; a Stalagmight schema upgrade with explicit permanent
numbering, changed UUIDs, live user edits and deleted leads; and compressed TML
whose start, closure and excluded comments must never import leads.

There is no fuzzy matching guarantee. A small measurement correction is safe
while another signature survives. Changing every native signature, including
both endpoints and measurements without a stable UUID, permits a new lead.
Compass file/survey renaming has the same limitation. Regression tests protect
this boundary so unrelated nearby leads are not silently merged.

The tests are discovered by the existing backend pipeline and CI without a new
runner or opt-in marker. Run the focused suite in the existing application
container:

```sh
docker exec -w /app speleodb-monorepo-django pytest \
  speleodb/gis/tests/test_exploration_lead_headings.py \
  speleodb/gis/tests/test_exploration_lead_directions_migration.py \
  speleodb/gis/tests/test_exploration_lead_import.py \
  speleodb/gis/tests/test_exploration_lead_pipeline.py \
  speleodb/gis/tests/test_exploration_lead_native_edges.py \
  speleodb/gis/tests/test_geojson_generation.py \
  speleodb/gis/tests/test_project_geojson_replacement.py \
  speleodb/surveys/tests/test_loop_closed_geojson.py
```

The complete backend gate remains
`docker exec -w /app speleodb-monorepo-django make test-py`. Missing PostgreSQL,
object storage or other required services are failures, never skipped coverage.

Schema and shared-library changes follow the existing SDK and standalone package
workflows. Consumers must resolve compatible published dependencies; local
monorepo overlays alone do not establish standalone availability. Package
publication, deployment and production recomputation are separate authorized
operations.
