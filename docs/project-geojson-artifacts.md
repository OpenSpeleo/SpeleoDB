# Survey GeoJSON colors and artifact revisions

Survey source history and rendered artifacts have different lifetimes. Ariane
and Compass Git commits identify source data; rebuilding their GeoJSON with a
new exporter can change its rendering properties without changing that commit.

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
private web viewer and mobile By Shot mode fall back to the owning survey's
color on each such shot. Other geometry properties, feature identities, survey
color settings and geometry/depth data retain their existing meanings.

## Metadata revision

`GET /api/v2/projects/geojson/` includes the read-only `geojson_revision` field
beside `geojson_file`. Both come from the same selected newest stored artifact.
Both are `null` when the project has no generated GeoJSON. Revision is the
SHA-256 hex digest of the storage-relative object name, an opaque equality token
that requires no schema migration or object download. It is not a content hash
or a Git commit SHA. New uploads use `<project UUID>/<artifact UUID>.json`,
within the field's existing 100-character limit. A fresh artifact UUID prevents
name reuse after deletion, including repeated rebuilds of the same source SHA.
Older stored paths remain readable. Renewed signed URLs for the same object keep
the same revision.

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
There is no automatic cleanup task or new database table. Operators can clean up
logged retired objects after rollout verification, only after all issued signed
URLs have expired (the GIS-view API allows up to 24 hours), active readers have
finished, and the object is confirmed absent from current artifact references.
Account for retained storage when scheduling large rebuilds; failed unpublished
replacement uploads are cleaned up immediately.

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

Verification covers both live upload exporters, historical regeneration,
unchanged geometry, same-commit revision changes, renewed URLs, null metadata,
bounded metadata queries, storage/database failures, pinned views and every OGC
cache family. Backend tests run in the existing application container.

## Exporter release handoff

The shot-color upload and regeneration paths require the new `compass_lib` and
`openspeleo_lib` exporters. The monorepo's live source overlays provide those
changes during integration development; the standalone web application's current
published dependency versions do not yet provide this feature.

When publication is authorized, release both Python libraries first. Then update
the standalone web application's PyPI version requirements and `uv.lock`, plus
the root integration lock. Keep web dependencies resolvable from PyPI in a
standalone clone; never add monorepo-relative library paths to its manifest. Run
the web upload/regeneration tests using the updated standalone dependencies and
again with the monorepo overlays, together with the libraries' own tests, before
deploying web or regenerating stored artifacts. The new actual-upload color
assertions deliberately require these exporter versions.

Deployment and production regeneration are separate authorized operations. After
deployment, follow the targeted verification and batch rollout in the
[build-command documentation](project-geojson-command.md); retain retired
objects until the cleanup conditions above are satisfied.
