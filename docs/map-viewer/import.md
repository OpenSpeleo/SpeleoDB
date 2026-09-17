# Importing places and map overlays

## Intent and design

The private map's **Import GPX/KML** action opens one accessible dialog with GPX
and KML/KMZ format tabs. GPX point records (`<wpt>`, called waypoints in the
file format) become landmarks; track records become GPS Tracks. The modal uses
**landmarks** consistently for those point locations. Its form introduces tracks
and landmarks as two independent outcomes before file selection. The destination
field follows the upload area and is explicitly labeled for landmarks only;
track imports never belong to a landmark collection. The collection help sits
between its label and select, with equal spacing above and below. KML/KMZ
requires an explicit intent choice:

| Choice      | Meaning                                                  | Destination                             |
| ----------- | -------------------------------------------------------- | --------------------------------------- |
| Placemarks  | Save point locations as independently editable landmarks | A writable landmark collection          |
| Map Overlay | Keep supported places, paths, and areas together         | Exactly one GIS Layer per uploaded file |

There is no automatic intent inference, combined output, or folder splitting.
KML points can be labels for polygon areas; geometry alone cannot establish the
user's desired outcome. Folder counts and geometry-part counts do not indicate
how many application GIS Layers to create. An overlay preserves its original
KML/KMZ for download, including content that the 2-D map cannot display.

The dialog is titled **Import GPX / KML-KMZ**. Before an intent is chosen, two
clickable cards describe the outcomes and give concrete examples. Each card is a
native button, supporting both pointer and keyboard selection. The destination
fields, upload area, export help, and import action stay hidden. Choosing a card
replaces the cards with the matching form and a compact mode summary. Its Change
button returns to the cards without discarding the file or inspection report.
Focus moves to Change after selection and back to the previously chosen card
when changing modes. Native collection selects have a contrasting fill and a
dedicated chevron so they are immediately recognizable as dropdowns. Color
distinguishes format navigation, intent selection, and primary actions without
relying on color alone.

The collection/name form adapts to the selected intent. Selecting a file starts
server inspection, then an inline review shows eligible content and
compatibility warnings. Switching intent reuses this report. A replacement file
invalidates the report and any outstanding response. Export instructions remain
collapsed directly above the collection/name field. Both modes share Google
Earth Pro’s Save Place As workflow, presented as three numbered steps in a
collapsible blue help panel. The first step adapts to the selected import mode;
menu actions and file formats are visually highlighted. Success and no-change
results persist until explicit dismissal.

## Ownership and interfaces

The shared KML/KMZ compiler owns parsing, normalized geometry, landmark
eligibility, diagnostics, and resource limits. The existing GIS compiler remains
an adapter to the same interpretation; there is no browser KML parser or second
server parser for landmarks.

- `POST /api/v2/import/kml_kmz/inspect/` accepts multipart `file`. It returns a
  compact report for both intents without coordinates, database writes, or
  durable storage. Existing collection duplicates are determined at
  confirmation.
- `PUT /api/v2/import/kml_kmz/` confirms landmark import using `file` and
  optional `collection`. It retains `landmarks_created` and reports skipped
  existing locations, in-file duplicates, destination, and bounds of newly
  created places.
- `POST /api/v2/gis-layers/` confirms overlay import using `source_file` and
  `name`. Existing publication owns the original source, generated display
  GeoJSON, creator ADMIN permission, and cleanup if publication fails.
- GPX uses its existing endpoint. Its success response includes `gps_track_ids`,
  `collection_id`, and combined `bounds` for newly created tracks and landmarks.
  Show on map reveals only those new tracks, reveals landmarks when created, and
  fits the imported extent. Crossing bounds are unwrapped for the map camera so
  date-line imports retain their short extent. Duplicate landmarks do not expand
  that extent. A track display failure leaves the import saved and allows
  another display attempt without republishing. Direct GeoJSON upload still
  stores one object without conversion.

Known malformed or unsupported KML input now receives a structured HTTP 422
processing response, including on the existing landmark PUT route; its old
generic HTTP 500 parse response is intentionally replaced. Unexpected failures
remain errors, and upload exceptions retain Sentry reporting. Successful legacy
landmark responses remain HTTP 200 with the existing `landmarks_created` field.

Inspection and confirmation are synchronous independent requests. Confirmation
validates the retained file again and rechecks destination permissions. There is
no staged upload, import-session model, worker, polling, or migration. The
second upload and parse are a deliberate tradeoff for avoiding temporary-data
ownership and job lifecycle infrastructure. Do not introduce those mechanisms
without a new product requirement and measured need.

The importer controller owns form state and transport. Shared dialog lifecycle
owns focus containment, fullscreen hosting, background isolation, and dismissal
guards. The import navigation module owns awaited map refresh and explicit
reveal/fit actions. Strict refresh options preserve cached lists on request
failure and expose the failure to the importer instead of replacing the map with
empty data.

The private map loads the scoped importer stylesheet through the registered
`style-map-import` Vite style entry, before controller initialization. Keep new
styles reachable from the logical style registry so both production loading and
the asset-graph check can verify them.

## Content rules

Placemarks mode accepts a Point or a nested MultiGeometry containing only
Points. A placemark mixing points with lines, polygons, or unsupported geometry
is excluded as a whole and reported. No centroids or line endpoints are
invented. Overlay mode retains supported vector geometry, polygon holes, and
existing folder metadata in one layer. Only actual document features are
importable: placemarks embedded in metadata or linked-document update commands
are excluded.

Coordinates retain the established rounding and collection-scoped uniqueness.
In-file duplicates use the first occurrence; existing landmark metadata is not
overwritten. Names and descriptions become plain text while retaining Unicode.
Long landmark names are shortened to the model limit with an aggregated warning;
blank names use the established timestamp fallback during confirmation.

Diagnostics distinguish unsupported content from display simplification, and are
aggregated at meaningful parent constructs. Known child fields do not generate
repeated unknown-element warnings. No external documents or assets are fetched.
KMZ selection prefers root `doc.kml`, otherwise the sole KML; an ambiguous
archive must be exported as one primary document.

Limits are centralized in the processing package. Upload, expanded primary KML,
and generated GeoJSON use the configured source-byte ceiling. Additional limits
bound archive entries, XML nesting, placemarks, and coordinate positions. A
bounded central-directory scan counts actual KMZ records before `ZipFile` can
allocate per-entry objects; declared entry counts alone are not trusted. Enforce
limits while reading/traversing and never decompress unused archive assets.

## Failure and interaction contracts

- Backdrop clicks do not dismiss uploads. Escape and explicit close work while
  idle; inspection can be abandoned without writes.
- Confirmation disables duplicate submission, form changes, and dismissal, and
  installs a temporary browser navigation warning. Remove it on every exit path.
- Show on map also blocks dismissal until loading and camera placement finish; a
  failed display restores the action without creating another import.
- Only transferred bytes receive percentage progress; server processing is
  indeterminate.
- A valid file with no eligible content has no enabled confirmation.
  All-existing landmarks are an accurate no-change result, not an error or an
  empty success.
- Landmark publication is transactional, including lazy personal-collection
  creation. Overlay publication compensates nontransactional object storage.
- An ambiguous transport failure must not trigger automatic resubmission.
- After success, refresh only affected categories without changing existing
  visibility, caches for existing overlays, or the camera. **Show on map** is
  the explicit reveal/fit action. A failed refresh offers refresh retry, never
  another import request.

## Verification

Parser tests cover real fixtures, point-only and mixed nested geometry, polygon
holes, accurate warnings, Unicode/HTML metadata, malformed XML, unsafe or
ambiguous archives, and limit boundaries with small configurable budgets. API
tests cover side-effect-free inspection, permissions, duplicates, exact source
preservation, one-file/one-layer publication, rollback, and legacy consumers.

Frontend tests cover intent and request state, stale responses, guarded
dismissal, safe DOM text, persistent results, strict refresh errors, and
explicit navigation. Browser checks exercise actual imports, source download,
keyboard, narrow/mobile layouts, fullscreen, and production assets. All tests
run inside the existing application container; full backend runs retain the
audited GitLab budget.

Measure representative parsing time and memory separately from browser
rendering. Changing display preferences must not trigger file reinspection or
feature rescans. Public and private viewers continue using their shared
rendering modules.

Fresh-process measurements in the local application container (Django startup
excluded from elapsed time; peak RSS includes Django):

| Fixture                                               | Analysis time | Peak RSS |
| ----------------------------------------------------- | ------------- | -------- |
| 736-place sample KML                                  | 0.370 s       | 226 MiB  |
| US states KMZ, 288 polygon parts                      | 0.881 s       | 262 MiB  |
| Protected areas KMZ, 366 points and 781 polygon parts | 3.756 s       | 400 MiB  |

The process baseline was approximately 221 MiB. Fixture inspection reports stay
below 3 KiB, enforced by regression tests. These observations describe analysis,
not a capacity guarantee or database-publication benchmark. Landmark publication
retains the existing per-coordinate transactional duplicate handling; large
landmark imports also incur database work.
