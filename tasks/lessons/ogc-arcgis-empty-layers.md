# OGC API - Features × ArcGIS Pro: empty-layer post-mortem

When ArcGIS Pro 3.6.1 ingested a SpeleoDB GIS-View OGC URL, every
project listed but every layer rendered empty. Live wire-data forensics
on the production endpoint refuted the obvious hypotheses (the `/items`
response was 48 KB of valid LineString features, no `?f=json` URL
corruption was happening) and surfaced **three independent OGC
compliance gaps in the response payload**:

1. The `/items` FeatureCollection had no `links[*][rel=self]`. OGC API
   Features 1.0 §7.16.2 normatively says **SHALL** include a `self`
   link. ArcGIS Pro 3.6 tightened OGC conformance checks; without
   `rel:self` it treats the response as incomplete and never commits
   features to the layer cache.
2. The response carried no `numberMatched` / `numberReturned` /
   `timeStamp`. ArcGIS uses these to drive its pagination state
   machine; absent values cause it to never finalise feature ingestion.
3. Each collection metadata document had no `crs`. The features carry
   3-D coordinates `[lon, lat, depth_metres]`. ArcGIS Pro defaults to
   2-D CRS84 unless the collection advertises `CRS84h` (the 3-D
   variant). Without it, Z values are silently stripped and (combined
   with #1 and #2) the layer renders empty.

## Lessons

* **OGC compliance is binary.** When the spec says SHALL, treat it as
  mandatory. ArcGIS Pro 3.6+ enforces compliance more strictly than 3.5
  did; partial conformance is worse than no advertisement at all
  because it triggers strict-mode validation on the client.
* **Cave data is 3-D.** Coordinate triples `[lon, lat, depth]` are the
  norm. Always advertise both `CRS84` and `CRS84h` in collection
  metadata so 2-D-only clients still work and 3-D-aware clients keep
  the Z values.
* **Per-request envelope, not per-cache.** OGC Req 29 says `timeStamp`
  is the response generation time. A cached envelope serves stale
  timestamps; cache the FEATURES list, build the envelope per-request.
  The `self` URL also varies under proxies that rewrite host/scheme,
  so caching the full response body breaks behind a CDN.
* **Don't advertise what you don't implement.** A Core conformance
  declaration commits to functional `bbox`/`limit`/`datetime`
  semantics. Silently ignoring those parameters is false advertising
  and breaks pagination. Either implement them properly or drop the
  conformance class.
* **Top-level Feature `id` matters.** RFC 7946 §3.2 says SHOULD;
  ArcGIS Pro relies on it for edit-tracking row identity. Lift
  `properties.id` to top-level during cache fill (one-time cost per
  commit SHA, not per request). Synthesize a deterministic
  `<sha>:<index>` if neither is present.
* **The user-facing URL must be the landing page.** Exposing a
  collections-list URL to QGIS / ArcGIS users violates the OGC
  discovery contract; clients can't run
  landing → conformance → collections → items if you hand them the
  collections endpoint directly. Same lesson is encoded in
  `tasks/lessons/ogc-qgis-discovery.md`.
* **Service-desc must point at a focused, cached document.** OGC Req 2
  requires every landing page to advertise `rel:service-desc` (or
  `rel:service-doc`). The live ArcGIS Pro 3.6.1 session pulled 684 KB
  of OpenAPI from `/api/schema/` per session — and the schema didn't
  even describe the OGC routes. The fix is **not** to drop the link
  (that breaks Req 2 conformance) but to ship a separate, focused
  OGC-only OpenAPI document at `/api/v2/gis-ogc/openapi/` shared by
  every family. Pre-build the bytes at import time, attach a strong
  ETag, ship `max-age=31536000` — across deploys clients short-circuit
  via `304 Not Modified`. See `speleodb/gis/ogc_openapi.py`.

## Architectural fix

The four OGC families (project view, project user, landmark single,
landmark user) used to each have their own landing/conformance/items
implementations. Now they all share `OGCFeatureService` (defined in
`speleodb/api/v2/views/ogc_base.py`) and the pure helpers in
`speleodb/gis/ogc_helpers.py`. Every compliance fix is written ONCE
and applies UNIFORMLY:

* `build_items_envelope` — `links` (self + collection + next/prev),
  `timeStamp`, `numberMatched`, `numberReturned`. Single source.
* `build_collection_metadata` — `crs` (CRS84 + CRS84h), `storageCrs`,
  `extent`. Single source.
* `parse_ogc_query` + `apply_ogc_query` — bbox, limit, offset,
  datetime, with `400 Bad Request` on malformed inputs. Single source.
* `normalize_features` — top-level Feature id lifting / synthesis.
  Single source.

## Test coverage

The regression-killer tests live in
`speleodb/api/v2/tests/test_ogc_compliance.py`:

* `TestProjectViewOGCCompliance.test_items_response_has_rel_self_link`
  — would have caught the live regression in CI.
* `TestArcGISPro361Replay.test_full_arcgis_discovery_sequence_round_trips`
  — reproduces the exact 4-request sequence from the production log
  with the actual ArcGIS Pro 3.6.1 user-agent.
* `TestOGCSchemaValidation.*` — every endpoint response is validated
  against an OGC JSON-schema fragment.
* `TestOGCSnapshots.*` — exact byte shape pinned with diff-on-failure.
* `TestOGCCrossTenantSecurity` — token A cannot access token B's data
  (404, never 403, so existence is not leaked).

The 100 % line + branch coverage gate (`make test-ogc-coverage`) and
the mutation-testing target (`make test-ogc-mutations`) keep the
contract honest.

## Deploy checklist (manual)

The synthetic test suite catches OGC-spec compliance gaps but does
NOT exercise the real network stack. Before declaring a deploy of any
change touching `speleodb/gis/ogc_helpers.py`, `speleodb/gis/ogc_openapi.py`,
or `speleodb/api/v2/views/ogc_base.py` complete, run the following
on the **staged** endpoint (not local-host):

1. **ArcGIS Pro 3.6.1 add-OGC-server smoke test.** Open ArcGIS Pro,
   *Insert > Connections > Add OGC API Features Server*, paste the
   GIS-View landing URL, then add at least one collection to a map.
   Expect: every layer renders features (not empty). If empty, capture
   network forensics with Charles/Fiddler and compare against
   `tasks/lessons/ogc-arcgis-empty-layers.md` known-cause section.

2. **QGIS 3.34+ add-OGC-API smoke test.** Same flow via *Layer > Add
   Layer > Add WFS / OGC API*. QGIS is more permissive than ArcGIS,
   but a failure here usually indicates a content-type or link-rel
   bug.

3. **OGC Team Engine** (`make test-ogc-teamengine`). Hits the staged
   endpoint with the official OGC API Features 1.0 conformance suite.
   Captures things hand-rolled JSON-Schema fragments will miss
   (e.g. landing-page `links[*].hreflang`, conformance class URI
   spelling). The Makefile target spins up the dockerised Team Engine
   and points it at `BASE_URL` from the environment.

4. **Wire-format check on bbox/datetime in pagination links.** From a
   shell with `httpie` or `curl`:
   ```
   http GET '<staged-host>/api/v2/gis-ogc/view/<token>/collections/<sha>/items?bbox=170,-10,-170,10&limit=2'
   ```
   Inspect the `links` block in the response for `rel:next` /
   `rel:prev`. The `bbox` and `datetime` parameters MUST contain
   literal commas (`,`), slashes (`/`), and colons (`:`) — never the
   percent-encoded `%2C`, `%2F`, `%3A` forms. ArcGIS Pro 3.6 has been
   seen to mis-parse the encoded forms on pagination follow-up.

5. **Cold-cache load test.** With Redis flushed, run a 50-RPS load
   against `/api/v2/gis-ogc/view/<token>/collections/<sha>/items`
   for 30 seconds. The lock in `_load_normalized_features` keeps S3
   reads bounded; verify CloudWatch S3 GET count stays under ~10
   for the test window.

Owner of any change in scope: file the artefacts of steps 1-4 in
the PR description (screenshots / pcap / curl transcript) before
merge. Skip step 5 only if the change does not touch
`_load_normalized_features` or its callers.
