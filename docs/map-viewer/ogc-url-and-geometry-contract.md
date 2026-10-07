# OGC API - Features: URL Convention & Geometry Split Contract

> Agent-focused reference for the URL shape and geometry-split design of the
> SpeleoDB OGC API - Features endpoints. Companion to
> `docs/map-viewer/api-reference.md` (which lists every endpoint) and the
> regression-killer tests in `speleodb/api/v2/tests/test_ogc_compliance.py`.

---

## 1. URL Convention — No Trailing Slashes

### The rule

Every OGC URL pattern in `speleodb/api/v2/urls/gis.py` MUST be slash-free. The
only exception is the static `openapi/` document (it's a bare-resource fetch,
not part of the OGC discovery contract). Pinned by
`test_no_ogc_url_pattern_has_inconsistent_trailing_slash`.

This applies to all four OGC families:

| Family                       | Landing URL (canonical)                           |
| ---------------------------- | ------------------------------------------------- |
| Project gis-view (gis_token) | `/api/v2/gis-ogc/view/<gis_token>`                |
| Project user (user_token)    | `/api/v2/gis-ogc/user/<key>`                      |
| Landmark single (gis_token)  | `/api/v2/gis-ogc/landmark-collection/<gis_token>` |
| Landmark user (user_token)   | `/api/v2/gis-ogc/landmark-collections/user/<key>` |

The trailing-slash variants (`view/<token>/`, etc.) **return 404**. Django's
`APPEND_SLASH` only adds slashes, never removes them — so the hard-break is by
design (see §1.3).

### Why this matters

SpeleoDB uses the same slash-free convention in Django routes, generated OpenAPI
paths, copied landing URLs, and discovery links. This prevents mismatched URL
construction and pins the interface used by its QGIS/ArcGIS regression fixtures.
It is a repository interoperability contract, not a claim that every OGC
implementation must use this URL style.

A trailing-slash landing request intentionally returns 404; no redirect strips
it. Django's `APPEND_SLASH` only adds a slash when that resolves a route. Users
with an old connection should re-copy the landing URL from the integration page.
The canonical route and its child discovery links are tested together.

### Verifying the convention is honoured

```bash
docker exec -w /app speleodb_local_django pytest speleodb/api/v2/tests/test_ogc_compliance.py::TestOGCURLCanonicalForm
```

The class pins:

- `test_landing_url_has_no_trailing_slash` — every `reverse(...)` result is
  slash-free.
- `test_landing_url_with_trailing_slash_returns_404` — the hard-break is
  asserted (not a 200, not a 301).
- `test_no_ogc_url_pattern_has_inconsistent_trailing_slash` — walks
  `urls/gis.py` and asserts the convention.
- `test_openapi_doc_path_templates_have_no_trailing_slash` — asserts the OpenAPI
  document agrees with the URL config.

---

## 2. Geometry Split Contract — One Collection per Geometry Group

### The split rule

Each project commit becomes **up to two** OGC collections, one per geometry
group actually present in the underlying GeoJSON:

- `<commit-sha>_points` — `Point`, `MultiPoint`
- `<commit-sha>_lines` — `LineString`, `MultiLineString`

A collection is only listed in `/collections` when the corresponding geometry
group has at least one feature in the GeoJSON (no empty layers). The mapping
`geometry-type → group` lives in `speleodb.gis.ogc_helpers.GEOMETRY_GROUPS`; the
URL routing layer enforces the shape via the `ogc_typed_id` converter (regex
`[0-9a-fA-F]{6,40}_(?:points|lines)`).

### Why two collections — even though it shows up as "two objects" in QGIS

SpeleoDB exposes station points and passage lines as independently typed
collections to avoid the mixed-layer interoperability failures encountered by
its GIS consumers. Tests pin discovery, uniform feature groups, and both point
and line availability. This does not assert that all GIS clients or the OGC
specification forbid mixed geometry. Users may group the two layers in their GIS
project for presentation without changing the service's collection identities.

### Why no polygons

SpeleoDB cave-survey data does not produce `Polygon` or `MultiPolygon`
geometries. The `GEOMETRY_GROUPS` mapping intentionally omits them so a stray
polygon (from a future ingest pipeline change) is **dropped with a structured
warning** rather than silently materialising an unexpected `_polygons`
collection that no other code is prepared to handle. Pinned by
`test_polygon_features_are_dropped_with_warning`.

Supporting polygons would be a product/API extension. Update `GEOMETRY_GROUPS`,
the `ogc_typed_id` converter, OpenAPI schemas/examples, migration-link
candidates, service assumptions, documentation, and positive/negative client
regression fixtures together. Verify actual discovery and rendering before
advertising the new group.

### Migration path for clients added before the split

The old per-commit collection lived at
`/api/v2/gis-ogc/<family>/<token>/collections/<sha>` with mixed geometries.
After the split, that exact URL returns **`410 Gone`** with a body that reads:

> This layer has been replaced — please re-add it from your OGC connection.
>
> SpeleoDB project layers used to combine point stations and line passages in a
> single OGC collection. To match how QGIS and ArcGIS Pro handle geometry types
> (one collection = one layer = one geometry type), each project is now exposed
> as up to two separate collections: `<commit-sha>_points` for stations and
> `<commit-sha>_lines` for passages.
>
> Action required: in your GIS client, REMOVE this layer and re-add it from the
> same OGC server connection — the collections list now shows the new `_points`
> and `_lines` layers in its place.

The response also carries a `Link` header
(`rel="alternate"; type="application/geo+json"`) listing every geometry-typed
replacement for the requested SHA, so OGC clients that follow Link headers can
self-migrate.

Those alternate links are migration candidates, not a fresh `/collections`
listing. The 410 view deliberately does not read the project GeoJSON just to
decide which geometry groups are present; a client that wants exact availability
should follow the landing page's `rel=data` link and use the live `/collections`
response.

`Cache-Control: no-store` is set on the 410 so clients never cache the migration
signal across deploys.

### Verifying the split contract is honoured

```bash
docker exec -w /app speleodb_local_django pytest speleodb/api/v2/tests/test_ogc_compliance.py::TestOGCGeometrySplit
```

The class pins:

- `test_collections_lists_one_per_geometry_group_present` — both groups present
  → exactly two collections, ids `<sha>_points` then `<sha>_lines` in the
  canonical order.
- `test_collections_omits_geometry_group_with_no_features` — empty layers are
  never advertised.
- `test_each_geometry_typed_collection_items_are_uniform` — every feature in a
  typed collection's `/items` matches the group.
- `test_polygon_features_are_dropped_with_warning` — the
  no-polygons-in-this-product invariant.
- `test_legacy_mixed_sha_collection_returns_410_with_link_header` — migration
  signal for stale clients.
- `test_legacy_mixed_sha_items_returns_410` — same for the items and
  single-feature variants.
- `test_geometry_split_bbox_is_per_subset` — per-group `extent.spatial.bbox`
  reflects the subset, not a shared union.
- `test_arcgis_pro_replay_through_geometry_typed_collection` — the four-step
  ArcGIS Pro discovery sequence end-to-end.

---

## 3. Why these two contracts live together

URL discovery and geometry typing share the OGC service boundary. Tests cover
both because a valid item payload is insufficient when a client cannot discover
it or interprets a mixed collection incorrectly. The canonical source modules,
regression classes above, and
[API verification guide](api-reference.md#35-conformance-and-verification) are
the maintained references; historical task notes are not part of the contract.

## 4. Performance implications

The geometry split adds one cache key per (commit_sha, artifact revision, group)
tuple for the per-group bbox (`ogc_geojson_bbox_<sha>_<revision>_<group>`) and
one key per stored artifact for the present-group set
(`ogc_geojson_groups_present_<sha>_<revision>`). The features list itself
remains a single cache entry per artifact
(`ogc_geojson_features_<sha>_<revision>`), filtered at request time by
`filter_features_by_geometry_group` (single-pass, O(n)). The `{id: feature}`
index and fill lock use the same revision and are shared across all groups.
Rebuilding GeoJSON at the same SHA cannot reuse an obsolete cache entry.
Synthetic feature ids are global per commit (`{sha}:{source-index}`), not
renumbered within each `_points` or `_lines` layer.

Project ETags also include that artifact revision, so same-commit rebuilds
return new content when clients revalidate. The request's metadata, ETag and
feature payload share one captured artifact. Retired storage objects remain
available to in-flight readers and previously issued signed URLs; see the
[artifact lifecycle and cleanup contract](../project-geojson-artifacts.md).

Warm-cache cost for `/collections` listing N projects is one groups-present
cache GET per project commit. Cold-cache discovery does load the normalized
feature list once per commit to compute which groups are present; the expensive
per-group bbox walk is still deferred to `/collections/{id}` per the same
rationale as the pre-split design — see
`ProjectViewOGCService.list_collections`.

## Response ownership and verification

`OGCFeatureService` and `ogc_helpers.py` own all four discovery families.
`build_items_envelope` builds response-specific self/collection/pagination
links, counts, and timestamps; cache normalized features rather than a host- or
time-specific envelope. `normalize_features` supplies stable top-level IDs,
while `parse_ogc_query`/`apply_ogc_query` own supported filtering and
pagination. Collection metadata and advertised capabilities must stay aligned
with those implementations.

Run focused OGC tests inside the existing application container. The repository
also provides coverage reporting, mutation, and staged Team Engine targets;
these are verification tools, not evidence of a completed conformance run or an
automatically enforced 100% coverage gate. Follow the API reference's
real-client smoke procedure for deployment changes. Verify pagination preserves
`bbox` and `datetime` values, including commas, interval slashes, and time
colons, and that following emitted links succeeds. When cache-fill code changes,
measure cold and warm storage reads under representative concurrent access. Do
not flush shared production caches or infer a capacity guarantee from an old
local load sample.
