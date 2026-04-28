# OGC API - Features: URL Convention & Geometry Split Contract

> Agent-focused reference for the URL shape and geometry-split design
> of the SpeleoDB OGC API - Features endpoints. Companion to
> `docs/map-viewer/api-reference.md` (which lists every endpoint) and
> the regression-killer tests in
> `speleodb/api/v2/tests/test_ogc_compliance.py`.

---

## 1. URL Convention — No Trailing Slashes

### The rule

Every OGC URL pattern in `speleodb/api/v2/urls/gis.py` MUST be
slash-free. The only exception is the static `openapi/` document
(it's a bare-resource fetch, not part of the OGC discovery
contract). Pinned by
`test_no_ogc_url_pattern_has_inconsistent_trailing_slash`.

This applies to all four OGC families:

| Family                              | Landing URL (canonical)                                       |
|-------------------------------------|---------------------------------------------------------------|
| Project gis-view (gis_token)        | `/api/v2/gis-ogc/view/<gis_token>`                            |
| Project user (user_token)           | `/api/v2/gis-ogc/user/<key>`                                  |
| Landmark single (gis_token)         | `/api/v2/gis-ogc/landmark-collection/<gis_token>`             |
| Landmark user (user_token)          | `/api/v2/gis-ogc/landmark-collections/user/<key>`             |

The trailing-slash variants (`view/<token>/`, etc.) **return 404**.
Django's `APPEND_SLASH` only adds slashes, never removes them — so
the hard-break is by design (see §1.3).

### Why this matters

The OGC API - Features 1.0 spec, GeoServer, pygeoapi, and ArcGIS
Server all use slash-free path templates. Two real failure modes
flow from a trailing slash on the landing URL:

1. **OpenAPI 3.0 path-template inconsistency.** OAS-driven clients
   construct request URLs as `<servers.url>` + `<paths.*>`. If
   landing is `/view/{token}/` and conformance is
   `/view/{token}/conformance`, joining yields
   `/view/{token}//conformance` → 404.
2. **GIS-client URL normalisation.** QGIS 3.34+ and ArcGIS Pro 3.6+
   construct child URLs by appending `/conformance`, `/collections`,
   etc. to the user-pasted landing URL. If the landing ends in `/`,
   naive concatenation produces a double slash (`view/<token>//conformance`)
   which 404s in production.

The historical regression and live forensics are documented in
`tasks/lessons/ogc-trailing-slash-and-geometry-split.md`.

### Why hard-break instead of redirect

Django's `APPEND_SLASH` middleware can only **add** trailing slashes
(turning `view/<token>` into `view/<token>/` when the latter
matches). It cannot strip them. So the user-facing options were:

* **(chosen) Hard-break.** Landing URL is `view/<token>` (no
  slash); requesting `view/<token>/` returns 404. The integration
  page renders the new URL automatically through `{% url %}`, so
  users re-copy once and the next paste works.
* **(rejected) Make every URL trailing-slash.** Would have
  re-introduced the OpenAPI inconsistency on the other end (sub-paths
  don't end in `/` per OGC convention).
* **(rejected) Custom middleware that strips trailing slashes.**
  Would silently mask future regressions instead of failing loudly.

### Verifying the convention is honoured

```bash
pytest speleodb/api/v2/tests/test_ogc_compliance.py::TestOGCURLCanonicalForm
```

The class pins:

* `test_landing_url_has_no_trailing_slash` — every `reverse(...)`
  result is slash-free.
* `test_landing_url_with_trailing_slash_returns_404` — the
  hard-break is asserted (not a 200, not a 301).
* `test_no_ogc_url_pattern_has_inconsistent_trailing_slash` —
  walks `urls/gis.py` and asserts the convention.
* `test_openapi_doc_path_templates_have_no_trailing_slash` —
  asserts the OpenAPI document agrees with the URL config.

---

## 2. Geometry Split Contract — One Collection per Geometry Group

### The split rule

Each project commit becomes **up to two** OGC collections, one per
geometry group actually present in the underlying GeoJSON:

* `<commit-sha>_points` — `Point`, `MultiPoint`
* `<commit-sha>_lines` — `LineString`, `MultiLineString`

A collection is only listed in `/collections` when the corresponding
geometry group has at least one feature in the GeoJSON (no empty
layers). The mapping `geometry-type → group` lives in
`speleodb.gis.ogc_helpers.GEOMETRY_GROUPS`; the URL routing layer
enforces the shape via the `ogc_typed_id` converter
(regex `[0-9a-fA-F]{6,40}_(?:points|lines)`).

### Why two collections — even though it shows up as "two objects" in QGIS

This is the universal GIS-client convention: **1 OGC collection
= 1 GIS layer = 1 uniform geometry type**. Every major platform
enforces it:

| Tool                            | Layer model                                                             |
|---------------------------------|-------------------------------------------------------------------------|
| QGIS (WFS / OGC API Features)   | One layer = one geometry type. Mixed → only one type renders.           |
| ArcGIS Pro / ArcGIS Server      | Feature classes have a fixed `geometry_type` set at creation.           |
| GeoServer                       | Publishes one layer per geometry type from the same PostGIS table.      |
| pygeoapi                        | Recommends one geometry type per collection in its docs.                |
| MapServer                       | `LAYER` block has a single `TYPE` (POINT, LINE, POLYGON).               |
| ESRI Shapefile                  | The format itself stores only one geometry type per file.               |

So serving a mixed-geometry collection wasn't merely "non-ideal" —
it was the actual bug from `tasks/lessons/ogc-arcgis-empty-layers.md`:
QGIS picked one geometry type and silently dropped the rest, leaving
the user with an "empty layer" they couldn't diagnose.

The "two objects" in QGIS is therefore the right outcome — and the
standard pattern GIS users have for every multi-geometry data
source. The usual UX softener is **client-side**:

* **In QGIS**: drag both collections into a Group in the Layers
  panel (right-click → "Group Selected"), collapse the group, and
  save the project. Visually appears as one expandable entry.
* **In ArcGIS Pro**: drag both into a Group Layer in the Contents
  pane.

Both clients persist the grouping in the project file, so users do
this once per project and never see the split again in their day-to-day
workflow.

### Why no polygons

SpeleoDB cave-survey data does not produce `Polygon` or
`MultiPolygon` geometries. The `GEOMETRY_GROUPS` mapping
intentionally omits them so a stray polygon (from a future ingest
pipeline change) is **dropped with a structured warning** rather
than silently materialising an unexpected `_polygons` collection
that no other code is prepared to handle. Pinned by
`test_polygon_features_are_dropped_with_warning`.

Adding a polygon group later is a one-line change:

1. Add `"polygons": frozenset({"Polygon", "MultiPolygon"})` to
   `GEOMETRY_GROUPS` in `speleodb/gis/ogc_helpers.py`.
2. Extend the `ogc_typed_id` converter regex to
   `[0-9a-fA-F]{6,40}_(?:points|lines|polygons)`.

The polygon-dropped warning will then stop firing, and the new
group will appear in `/collections` automatically for any project
whose GeoJSON contains polygons.

### Migration path for clients added before the split

The old per-commit collection lived at
`/api/v2/gis-ogc/<family>/<token>/collections/<sha>` with mixed
geometries. After the split, that exact URL returns **`410 Gone`**
with a body that reads:

> This layer has been replaced — please re-add it from your OGC
> connection.
>
> SpeleoDB project layers used to combine point stations and line
> passages in a single OGC collection. To match how QGIS and
> ArcGIS Pro handle geometry types (one collection = one layer =
> one geometry type), each project is now exposed as up to two
> separate collections: `<commit-sha>_points` for stations and
> `<commit-sha>_lines` for passages.
>
> Action required: in your GIS client, REMOVE this layer and
> re-add it from the same OGC server connection — the collections
> list now shows the new `_points` and `_lines` layers in its
> place.

The response also carries a `Link` header
(`rel="alternate"; type="application/geo+json"`) listing every
geometry-typed replacement for the requested SHA, so OGC clients
that follow Link headers can self-migrate.

Those alternate links are migration candidates, not a fresh
`/collections` listing. The 410 view deliberately does not read the
project GeoJSON just to decide which geometry groups are present; a
client that wants exact availability should follow the landing page's
`rel=data` link and use the live `/collections` response.

`Cache-Control: no-store` is set on the 410 so clients never cache
the migration signal across deploys.

### Verifying the split contract is honoured

```bash
pytest speleodb/api/v2/tests/test_ogc_compliance.py::TestOGCGeometrySplit
```

The class pins:

* `test_collections_lists_one_per_geometry_group_present` — both
  groups present → exactly two collections, ids
  `<sha>_points` then `<sha>_lines` in the canonical order.
* `test_collections_omits_geometry_group_with_no_features` — empty
  layers are never advertised.
* `test_each_geometry_typed_collection_items_are_uniform` — every
  feature in a typed collection's `/items` matches the group.
* `test_polygon_features_are_dropped_with_warning` — the
  no-polygons-in-this-product invariant.
* `test_legacy_mixed_sha_collection_returns_410_with_link_header` —
  migration signal for stale clients.
* `test_legacy_mixed_sha_items_returns_410` — same for the items
  and single-feature variants.
* `test_geometry_split_bbox_is_per_subset` — per-group
  `extent.spatial.bbox` reflects the subset, not a shared union.
* `test_arcgis_pro_replay_through_geometry_typed_collection` —
  the four-step ArcGIS Pro discovery sequence end-to-end.

---

## 3. Why these two contracts live together

Both regressions originated from the same hardening commit
(`06032e70`, Apr 27 2026): the trailing slash on the landing URL
broke OGC client URL construction, and the mixed-geometry
collection broke layer rendering. They are independent failure
modes but share a root cause — a SpeleoDB-internal API shape that
worked in unit tests but mismatched what real GIS clients expect.

The lesson document
`tasks/lessons/ogc-trailing-slash-and-geometry-split.md` captures
the regression history so a future agent can't reintroduce either
issue without tripping the regression-killer tests above.

## 4. Performance implications

The geometry split adds one cache key per (commit_sha, group)
tuple for the per-group bbox
(`ogc_geojson_bbox_<sha>_<group>`) and one cache key per
commit_sha for the present-group set
(`ogc_geojson_groups_present_<sha>`). The features list itself
remains a single cache entry per SHA
(`ogc_geojson_features_<sha>`), filtered at request time by
`filter_features_by_geometry_group` (single-pass, O(n)). The
`{id: feature}` index is unchanged and is shared across all groups
for the same SHA. Synthetic feature ids are global per commit
(`{sha}:{source-index}`), not renumbered within each `_points` or
`_lines` layer.

Warm-cache cost for `/collections` listing N projects is one
groups-present cache GET per project commit. Cold-cache discovery
does load the normalized feature list once per commit to compute which
groups are present; the expensive per-group bbox walk is still deferred
to `/collections/{id}` per the same rationale as the pre-split design
— see `ProjectViewOGCService.list_collections`.
