# GIS navigation section

Follow-up: [GIS Tooling disclosure](gis-tooling-collapse.md) moves Survey Map
back to the first section and makes the remaining second section collapsible.

- [x] Inspect desktop/mobile navigation, current labels, docs, tests, and
      lessons.
- [x] Move GIS Geometries and GIS Layers to the second section without the My
      prefix; alphabetize the GIS section.
- [x] Update current documentation and supersede stale navigation guidance.
- [x] Verify sidebar order, links, active route states, and shared responsive
      markup; run relevant Python/frontend tests, lint, and production build in
      the application container.
- [x] Review the final diff independently and record results.

Plan: retain the shared `base_private.html` sidebar used by the mobile drawer
and desktop navigation. Move whole menu blocks, preserving icons, destinations,
and route-family active states. The GIS group orders Cylinder Fleets,
Experiments, Geometries, Landmark Collections, Layers, Sensor Fleets, Station
Tags, Surface Monitoring, Survey Map, and Views. Listing-page headings remain
their existing titles; this request changes navigation.

## Review

Moved complete navigation blocks and alphabetized the GIS section in the shared
desktop/mobile sidebar. Updated feature docs, navigation guidance, and the old
ordering lesson; marked the historical task superseded. Existing page-heading
tests remain applicable. Independent review found no correctness issues.

Verification in `speleodb_local_django`:

- 125 focused Python tests passed across template, GIS layer/geometry, and
  dashboard views. Final template regression rerun: 27 passed.
- All 1,191 JavaScript tests passed.
- Template formatting/lint, JavaScript lint, Ruff check/format, focused mypy,
  clean production build, and `git diff --check` passed.
- GitLab audit reports zero creations, zero creation POSTs, zero violations, and
  no unresolved outcomes; no remote cleanup was required.
- Tests verify section ordering, unique destinations, all eight layer/geometry
  active routes, and shared desktop/mobile visibility. No browser visual run.
