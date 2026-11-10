# Survey GeoJSON colors and artifact revisions

Survey source history and rendered artifacts have different lifetimes. Ariane,
Compass, and Stalagmight Git commits identify source data; rebuilding their
GeoJSON with a new exporter can change its rendering properties without changing
that commit.

## Upload and background generation

Uploads save and push source data before recording optional map-generation work.
Generation runs in Celery after the source database transaction commits. Upload
success does not require a usable map. The status API reports pending/failed
generation, and the last successful artifact remains available. See
[background generation](project-geojson-background.md) for ordering,
diagnostics, worker recovery, and testing.

## Shot color contract

Each exported survey LineString can carry `properties.color`, a CSS color
string. Ariane's original shot colors are normalized to lowercase `#rrggbb`, or
`rgba(r,g,b,a)` when the source includes transparency. Missing or invalid colors
are omitted. Compass randomly assigns one vibrant color to each section and
exports it on its shots, independently of the existing `stroke`/origin styling
options. Assignments use fresh random choices without a seed, source hash or
algorithm version; regenerating the same source can change its colors.

Compass tries at most 16 palette passes. It retains a candidate only when more
sections receive non-conflicting colors, stops when all sections are colored,
and stops early when a pass makes no improvement. Unresolved sections then use
distinct extra vivid colors. This fallback examines at most the unresolved
section count plus the number of colors already used, which is sufficient to
complete coloring while the finite vivid RGB space has capacity. Touching
sections therefore remain distinct after the palette-pass budget is exhausted.
Only exhaustion of that entire RGB pool leaves unresolved sections without
`color`; the export still completes and those sections use the viewer's survey
fallback, which can display them with the same color.

Consumers must tolerate old artifacts with no color and malformed values. The
private web viewer and mobile By Section mode fall back to the owning survey's
color on each such shot. Other geometry properties, feature identities, survey
color settings and geometry/depth data retain their existing meanings.

## Metadata revision

`GET /api/v2/projects/geojson/` includes the read-only `geojson_revision` field
beside `geojson_file` and `geojson_commit_sha`. All three come from the same
selected newest stored artifact and are `null` when the project has no generated
GeoJSON. The artifact SHA can differ from source `latest_commit` while
generation is pending or has failed. Revision is the SHA-256 hex digest of the
storage-relative object name, an opaque equality token that requires no schema
migration or object download. It is not a content hash or a Git commit SHA. New
uploads use `<project UUID>/<artifact UUID>.json`, within the field's existing
100-character limit. A fresh artifact UUID prevents name reuse after deletion,
including repeated rebuilds of the same source SHA. Older stored paths remain
readable. Renewed signed URLs for the same object keep the same revision.

The endpoint reuses its ordered artifact prefetch to select that row once,
without an extra query for each revision or download URL. Ordinary project and
historical commit metadata endpoints retain their existing shapes.

Mobile clients compare this revision with the revision saved alongside the
downloaded payload, including when the survey commit has not changed. They only
advance the cached revision after successful download, validation and cache
replacement. Offline use and failed refreshes retain the previous artifact.
Older servers may omit the field, so clients retain their existing commit-based
refresh behavior when no revision is advertised.

## Regeneration and caching

The [build command](project-geojson-command.md) generates and uploads first,
then atomically replaces the immutable artifact row at the same commit. A failed
replacement leaves the previous artifact available. GIS views pin their project
and source SHA and therefore survive artifact replacement.

Successfully superseded immutable objects remain stored. Deleting one as soon as
the row changes would break already issued signed URLs and in-flight OGC readers
holding that artifact. Each successful replacement logs the retired object key.
Object retirement has no automatic cleanup task or dedicated tracking table.
Operators can clean up logged retired objects after rollout verification, only
after all issued signed URLs have expired (the GIS-view API allows up to 24
hours), active readers have finished, and the object is confirmed absent from
current artifact references. Account for retained storage when scheduling large
rebuilds. Failed unpublished replacement uploads attempt immediate cleanup;
asynchronous generation also journals them for delayed cleanup after a hard kill
or storage outage, as described in
[background generation](project-geojson-background.md).

OGC normalized features, single-feature indexes, geometry-group discovery,
bounds and cache-fill locks include both source SHA and artifact revision. A
reader carries one captured artifact through nested cache and storage accesses.
An in-flight old reader can only fill its old revision namespace; subsequent
requests resolve the replacement. Old keys expire under the existing 24-hour
TTL, without a global cache purge. Discovery reuses prefetched artifact rows,
and cached single-feature lookups retain their constant-time index access.

Project OGC ETags contain `<source SHA>_<geometry group>_<artifact revision>`.
Each request keeps the same artifact for metadata, ETag, features and individual
feature lookups. A replacement during the request can therefore finish serving
the old representation consistently. A later request with the old ETag receives
the replacement content and its new ETag, including for same-commit rebuilds.

Object downloads use the replacement object's new path. Existing OGC HTTP
responses retain their current cache headers, so external clients may display
old content until revalidation or their existing cache lifetime expires. Users
with downloaded offline maps retain survey-color fallback until they refresh.

Verification covers all supported live upload exporters, historical
regeneration, unchanged geometry, same-commit revision changes, renewed URLs,
null metadata, bounded metadata queries, storage/database failures, pinned views
and every OGC cache family. Backend tests run in the existing application
container.

## Exporter availability and regeneration

The standalone web application's manifest and lock select the published
exporters. Compass generates section colors; Ariane preserves valid source
colors; Stalagmight uses OpenSpeleo's normalized native section colors and
common GeoJSON properties. Confirm the server performing regeneration has the
pinned exporters installed. Dependency updates do not add colors to previously
stored GeoJSON: artifacts without `properties.color` still need explicit
regeneration, even when the source commit is unchanged.

Keep web dependencies resolvable from PyPI in a standalone clone; never add
monorepo-relative library paths to its manifest. Validate exporter changes with
the web upload/regeneration tests using standalone dependencies and again with
the monorepo overlays, together with the libraries' own tests.

Deployment and production regeneration are separate authorized operations.
Follow the targeted verification and batch rollout in the
[build-command documentation](project-geojson-command.md); retain retired
objects until the cleanup conditions above are satisfied.

Full history reset is an explicit exception to retired-object retention: it
purges the project namespace, including current, retired and orphaned objects,
verifies emptiness, and rebuilds from the existing remote. Previously issued
links may stop working. See [Operations](admin-operations.md).

## Project list metadata loading

The authenticated GeoJSON project list loads commit metadata, commit counts,
active mutexes with their owners, and file formats in bulk using the existing
Project queryset helpers. Its inherited serializer must not query these
relations once per project. Artifact ordering and URL/revision pairing remain
unchanged. The endpoint query regression asserts actual accessible records and
mutex/commit values while comparing query counts as projects are added. OGC
callers do not load these unrelated serializer fields.

## Historical map links

Revision history offers a dedicated read-only map for each commit that has a
stored GeoJSON artifact. Desktop and mobile actions use the same full source
SHA. The authenticated map route scopes both commit and artifact to the selected
project and requires at least `READ_ONLY`, including active team grants.
`WEB_VIEWER` users cannot open historical maps. Revision history, source
downloads, and Git browsing retain their existing permission requirements. The
primary “View history on map” action opens the most recent non-creation commit
in the historical viewer. If it has no artifact, the viewer shows its
unavailable state rather than substituting an older commit. Projects with no
visible commits have no main map action.

The historical map's Project History panel lists recorded history in canonical
newest-first date order, excluding only commits with message
`[Automated] Project Creation` and author `SpeleoDB`, matching the
revision-history page. Dates, short truncated messages and authors identify
revisions; each card shows its date, time, message and author. The page heading
shows only the project name. The panel sizes to its content within the map width
and shares the private project panel's styling, header divider and spacing;
commit hashes remain in URLs and inert data only. The selected revision is
highlighted, and choosing another available revision replaces the survey in the
existing map without reloading the page. The camera refocuses on the selected
survey while display settings remain in place. Revisions without generated
artifacts remain visible as unavailable entries. History metadata and artifacts
are loaded in one joined query, and each available artifact receives its own
signed download URL after project access is checked. URLs and revision
identities are inert metadata; switching requires no new REST endpoint.

The HTML response is private and non-cacheable. Each signed artifact URL has the
existing one-hour lifetime. The selected revision shares the exact signed URL
from its history entry with the shared read-only renderer. Refreshing the page
rechecks access and renews the history artifact URLs. Regeneration can replace
that artifact; a historical link does not preserve older exporter outputs.
Basemap changes retain the selected survey. Current annotations and editing
tools are excluded.

Missing artifacts show an unavailable page and never fall back to the newest
survey or trigger conversion. Existing administrator generation tools remain
responsible for creating or repairing artifacts. The separate revision-history
listing still loads availability in one project-scoped query without signing
artifact URLs. The historical map request performs indexed lookups without Git
access, conversion, or a new API endpoint. Regression tests cover exact
older-artifact storage readback, direct and team permissions, revoked access,
cross-project isolation, and missing-map behavior.
