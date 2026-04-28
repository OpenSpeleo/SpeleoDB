# OGC API - Features: trailing slash + geometry split post-mortem

In April 2026 the Apr 27 hardening commit (`06032e70`,
"Harden OGC API - Features layer …") preserved a historical
inconsistency in the OGC URL surface that — combined with how QGIS /
ArcGIS Pro construct child URLs and render mixed-geometry
collections — produced two distinct user-visible regressions on the
same code path.

This file is the regression-killer reference for future agents
touching anything in `speleodb/api/v2/urls/gis.py`,
`speleodb/api/v2/views/ogc_base.py`, `speleodb/api/v2/views/gis_view.py`,
`speleodb/api/v2/views/project_geojson.py`, `speleodb/gis/ogc_helpers.py`,
or `speleodb/gis/ogc_openapi.py`.

## Symptom 1 — "Nothing works" after the hardening commit

User report: "We recently worked on refactoring the OGC GIS endpoints
— nothing works anymore because the main endpoints finishes with a
slash."

### Root cause

`speleodb/api/v2/urls/gis.py` had four landing patterns ending in
`/` (e.g. `path("view/<gis_token:gis_token>/", …)`) while every
sub-endpoint was slash-free (e.g.
`path("view/<gis_token:gis_token>/conformance", …)`). The OpenAPI
document built in `speleodb/gis/ogc_openapi.py::_build_paths_for`
mirrored the inconsistency (`f"{prefix}/"` for landing,
`f"{prefix}/conformance"` for sub-paths).

QGIS 3.34+ and ArcGIS Pro 3.6+ construct child URLs by appending
`/conformance`, `/collections`, `/collections/<id>/items`, etc. to
the landing URL the user pasted. With the trailing slash on the
landing URL, naive concatenation produced
`view/<token>//conformance` (double slash) → 404 in production.
OAS-driven clients had the same failure mode joining
`servers.url` + `paths.*`.

### The trailing-slash fix

Single canonical convention: **every OGC URL pattern is slash-free**
(except the static `openapi/` document, which is a bare-resource
fetch). Pinned at three layers:

1. URL routing (`urls/gis.py`): `path("view/<gis_token:gis_token>", …)`.
2. OpenAPI doc (`ogc_openapi.py::_build_paths_for`): landing template
   is `prefix`, not `f"{prefix}/"`.
3. Convention test
   (`test_no_ogc_url_pattern_has_inconsistent_trailing_slash`):
   walks `urlpatterns` and fails CI if any future agent re-adds a
   trailing slash.

**No `APPEND_SLASH` redirect to soften the migration.** Django's
`APPEND_SLASH` only adds slashes, never removes them, so a request
for the trailing-slash form returns 404 — the intended user-facing
signal so existing setups stop silently misbehaving. The integration
page renders the new URL automatically through `{% url %}`, so
users re-copy once and the next paste works.

### Trailing-slash regression-killer tests

In `speleodb/api/v2/tests/test_ogc_compliance.py`:

* `TestOGCURLCanonicalForm.test_landing_url_has_no_trailing_slash`
* `TestOGCURLCanonicalForm.test_landing_url_with_trailing_slash_returns_404`
* `TestOGCURLCanonicalForm.test_no_ogc_url_pattern_has_inconsistent_trailing_slash`
* `TestOGCURLCanonicalForm.test_openapi_doc_path_templates_have_no_trailing_slash`

## Symptom 2 — Mixed-geometry collections render as empty layers

User report (also from the original ArcGIS empty-layer post-mortem,
`tasks/lessons/ogc-arcgis-empty-layers.md`): "QGIS / ArcGIS Pro
are not able to load our GeoJSON because they contain a mix of
points and lines."

### Geometry-split root cause

Each project commit was exposed as a single OGC collection
(`<sha>`) containing both Point/MultiPoint stations and
LineString/MultiLineString passages. The OGC API - Features
specification permits this, but every major GIS client maps **one
OGC collection → one map layer → one geometry type** at the layer
schema level:

* QGIS WFS / OGC API Features layers have a fixed geometry type;
  mixed responses get one type rendered, the rest silently dropped.
* ArcGIS Pro 3.6 feature classes have `geometry_type` baked in at
  creation.
* GeoServer publishes one layer per geometry type from the same
  PostGIS table, even when the underlying SQL view returns mixed.
* pygeoapi recommends "one geometry type per collection" in its
  docs.
* MapServer `LAYER` blocks have a single `TYPE`.
* ESRI Shapefile stores one geometry type per file at the format
  level.

So the previous "single mixed `<sha>` collection" wasn't merely
non-conventional — it actively broke layer rendering on the most
common GIS clients used by SpeleoDB users.

### The geometry-split fix

Split per-project collections by geometry group:

* `<commit-sha>_points` — `Point`, `MultiPoint`
* `<commit-sha>_lines` — `LineString`, `MultiLineString`

Implementation surface:

* New URL converter `ogc_typed_id` in
  `speleodb/utils/url_converters.py`
  (regex `[0-9a-fA-F]{6,40}_(?:points|lines)`).
* New helpers in `speleodb/gis/ogc_helpers.py`: `GEOMETRY_GROUPS`,
  `classify_geometry`, `parse_typed_collection_id`,
  `filter_features_by_geometry_group`, `geometry_groups_present`,
  `collection_bbox_2d_for_group`.
* `ProjectViewOGCService.list_collections` and
  `ProjectUserOGCService.list_collections` enumerate one
  `OGCCollectionMeta` per (commit_sha, group) tuple actually
  present (no empty layers).
* `OGCLegacyMixedCollectionGoneView` returns `410 Gone` on the
  pre-split `<sha>` URL with a `Link: rel="alternate"` header
  listing the geometry-typed replacements and a body that reads
  like a user-facing migration prompt (QGIS / ArcGIS Pro display
  the body to the human user).
* Cache keys are suffixed with the group
  (`ogc_geojson_bbox_<sha>_<group>`) so the per-group bbox stays
  cheap; the features list itself remains a single
  per-SHA cache entry filtered at request time.

### Why no polygons

SpeleoDB cave-survey data does not produce `Polygon` /
`MultiPolygon` geometries. `GEOMETRY_GROUPS` intentionally omits
them so a stray polygon (from a future ingest pipeline change) is
**dropped with a structured warning** rather than silently
materialising an unexpected `_polygons` collection that no other
code is prepared to handle. Adding a polygon group later is a
one-line change to `GEOMETRY_GROUPS` plus the
`ogc_typed_id` regex — no architectural rework.

### Geometry-split regression-killer tests

In `speleodb/api/v2/tests/test_ogc_compliance.py`:

* `TestOGCGeometrySplit.test_collections_lists_one_per_geometry_group_present`
* `TestOGCGeometrySplit.test_collections_omits_geometry_group_with_no_features`
* `TestOGCGeometrySplit.test_each_geometry_typed_collection_items_are_uniform`
* `TestOGCGeometrySplit.test_polygon_features_are_dropped_with_warning`
* `TestOGCGeometrySplit.test_legacy_mixed_sha_collection_returns_410_with_link_header`
* `TestOGCGeometrySplit.test_legacy_mixed_sha_items_returns_410`
* `TestOGCGeometrySplit.test_geometry_split_bbox_is_per_subset`
* `TestOGCGeometrySplit.test_arcgis_pro_replay_through_geometry_typed_collection`

## Lessons

* **The OGC URL surface is the contract — and the contract must be
  consistent.** A landing URL that ends in `/` is internally
  consistent with itself but inconsistent with everything else
  (sub-paths, OpenAPI templates, GIS-client URL construction). Pick
  one shape, enforce it at three layers (URL config, OpenAPI doc,
  convention test).
* **GIS clients are stricter than the OGC spec.** The spec permits
  mixed-geometry collections; QGIS / ArcGIS Pro do not render them
  correctly. When the spec is permissive and clients are strict,
  the implementation MUST follow the clients (else the spec
  conformance is theatre).
* **`APPEND_SLASH` is a one-way hammer.** It only adds trailing
  slashes, never removes them. Don't lean on it as a soft-migration
  mechanism for a slash-removal change — it won't help, and silently
  surfacing 404s for the trailing-slash form is the right
  user-facing signal anyway.
* **410 Gone with a Link header is the OGC-compliant migration
  signal**, but the response body is what GIS clients display to
  the human user — write it as a user message, not a developer
  note. The body should answer "what do I do now?" (re-add the
  layer in QGIS), not "what HTTP semantic was violated?".
* **Cache keys must include every dimension the response varies
  over.** When the response now varies by `(sha, group)` instead
  of just `sha`, every bbox / index / metadata cache key needs the
  group suffix. The features-list cache key DOES NOT need the
  group (a single per-SHA list is filtered at request time) — that
  decision should be explicit in the docstring.

## Architectural fix (where the contract lives)

Single source of truth for each piece of the contract:

* **URL convention (no trailing slashes)**:
  `speleodb/api/v2/urls/gis.py` (URL config),
  `speleodb/gis/ogc_openapi.py::_build_paths_for` (OAS doc),
  `TestOGCURLCanonicalForm` (regression-killer).
* **Geometry split (one collection per group present)**:
  `speleodb/gis/ogc_helpers.py::GEOMETRY_GROUPS` (the actual
  mapping), `speleodb/utils/url_converters.py::OGCTypedCollectionIdConverter`
  (URL routing enforcement),
  `speleodb/api/v2/views/gis_view.py::ProjectViewOGCService` and
  `speleodb/api/v2/views/project_geojson.py::ProjectUserOGCService`
  (service-layer enumeration), `OGCLegacyMixedCollectionGoneView`
  (migration signal), `TestOGCGeometrySplit` (regression-killer).

The user-facing contract is documented in
`docs/map-viewer/ogc-url-and-geometry-contract.md`. The endpoint
table in `docs/map-viewer/api-reference.md` reflects the URL
shape; the mixed-geometries paragraph there points at this lesson
for the "why".

## Deploy checklist (manual, post-CI)

The synthetic test suite catches every spec/contract regression
documented above but does NOT exercise the real network stack.
Before declaring a deploy of any change touching the URL config,
the OpenAPI doc, the geometry helpers, or the OGC service classes
complete, run the four-step smoke test in
`tasks/lessons/ogc-arcgis-empty-layers.md` (Deploy checklist
section) on the **staged** endpoint. The replay test pins each of
those steps in CI; the manual smoke is a safety net for things the
synthetic suite cannot model (real CDN, real proxy, real ArcGIS
Pro user-agent quirks).

## Adversarial review findings

* `speleodb/api/v2/tests/test_ogc_compliance.py:29` — local `PLC0415` imports hid a repository rule violation; top-level imports plus `ruff check` now prevent recurrence.
* `speleodb/api/v2/tests/test_gis_view_api.py:1900` — stale streaming-response `type: ignore` comments were no longer needed; focused `mypy` now prevents dead suppressions from accumulating.
* `speleodb/api/v2/views/landmark_collection_ogc.py:119` — a pre-existing serializer return `type: ignore` had gone stale; focused `mypy` now prevents the OGC chain from carrying unused suppressions.
* `speleodb/gis/ogc_helpers.py:84` — `build_landing_page()` carried a local `OGC_OPENAPI_PATH` import to dodge a cycle; the constant now lives with the helper constants and top-level imports prevent recurrence.
* `speleodb/gis/ogc_helpers.py:656` — the unsupported-geometry warning claimed to be structured but only formatted a string; stable `extra` fields plus `test_polygon_features_are_dropped_with_warning` now prevent recurrence.
* `speleodb/api/v2/tests/test_ogc_compliance.py:3272` — empty group presence was not regression-pinned as a cache hit; the empty-tuple cache test now prevents recomputing or confusing `()` with a miss.
* `speleodb/api/v2/tests/test_ogc_compliance.py:3293` — the legacy 410 `Link` header was only substring-checked; parseable two-entry alternate assertions now prevent malformed migration headers.
* `speleodb/api/v2/tests/test_ogc_compliance.py:3323` — HEAD on the legacy mixed SHA URL was not pinned; the HEAD regression test now prevents losing the 410 migration signal for header-only clients.
* `speleodb/api/v2/tests/test_ogc_compliance.py:2811` — OpenAPI path resolution only exercised `_lines`; materialising both `_points` and `_lines` now prevents suffix-specific converter drift.
* `speleodb/api/v2/tests/test_gis_view_api.py:2053` — discovery-flow tests accepted any non-empty collection list; exact `_points` plus `_lines` assertions now prevent silently losing one geometry layer.
* `speleodb/api/v2/tests/test_gis_view_api.py:2284` — a no-permission test requested a missing `_lines` layer from a point-only fixture; requesting the existing `_points` layer now proves permission denial, not group absence.
* `speleodb/api/v2/tests/test_landmark_collection_ogc.py:148` — Landmark tests depended on link order; selecting links by `rel` now prevents harmless link reordering from breaking or masking behavior.
* `docs/map-viewer/ogc-url-and-geometry-contract.md:254` — the performance doc falsely claimed cold `/collections` had no S3 read; the corrected warm-vs-cold wording now matches `_load_geometry_groups_present`.
* `docs/map-viewer/api-reference.md:302` — the API reference had a stale release date and singular-layer smoke wording; typed `_points`/`_lines` smoke steps now prevent reintroducing mixed-layer expectations.
* `tasks/lessons/ogc-arcgis-empty-layers.md:134` — manual runbook examples still used legacy `<sha>/items`; typed `<sha>_lines/items` examples now prevent operators from smoke-testing a 410 URL.
* `speleodb/api/v2/tests/test_gis_view_api.py:1452` — fixture docs still said polygons round-trip; the corrected comment now matches the no-polygons contract.
* `docs/map-viewer/ogc-url-and-geometry-contract.md:188` — the 410 `Link` header over-advertises candidate geometry groups by design; documenting candidates versus live `/collections` now prevents future DB/S3 work in the gone view.
* `docs/map-viewer/ogc-url-and-geometry-contract.md:250` — synthetic IDs were not documented as global per commit; the note now prevents clients and agents from assuming per-layer dense row numbers.
