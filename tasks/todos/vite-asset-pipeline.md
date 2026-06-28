# Unified Vite Asset Pipeline

## Goal

Replace the standalone Tailwind CLI, separate esbuild pipelines, polling
watcher, and direct first-party asset loading with one Vite build graph. Django
continues to render HTML and serve static assets. The migration must not change
product appearance, behavior, accessibility, route ownership, or security.

## Baseline contract

- Branch: `dsf` (must not change).
- Starting commit: `c1977452ee0e6dc259ea893c683ca47a56cef662`.
- Baseline source: the preserved Git index materialized at
  `/private/tmp/speleodb-vite-baseline.OKm1Xa`.
- Cached diff SHA-256:
  `b09090ce23f3e27e5f0457bad863c887d2955545e1755dda0713e1105a75ed88`.
- Index SHA-256:
  `f38caf10b44e68afbc754e775819eef4314f6fd6236b3f4e09f03c83c1e328d0`.
- Initial state: 47 staged paths, no unstaged changes. All Vite work remains
  unstaged and both migration prompt files remain preserved.
- Initial inventory: 134 first-party/vendor CSS, JS, and TS files; 69 template
  files containing script elements; 46 template files containing style blocks.

## Checklist

### Baseline and inventory

- [x] Record branch, commit, staged/unstaged/ignored state, and index hashes.
- [x] Materialize the exact index without switching branches or touching it.
- [x] Build the isolated baseline and record CSS/JS hashes and sizes.
- [x] Classify every CSS/JS/TS file as first-party entry, transitive source,
  test, third-party external, generated output, or proven dead source.
- [x] Inventory every template static reference, executable inline block,
  static style block, application event attribute, runtime-generated event
  attribute, and global API.

### Vite foundation

- [x] Add exact Vite and Tailwind Vite dependencies and audit install scripts.
- [x] Add one root Vite config and one logical entry registry.
- [x] Emit production hashes, development-stable names, shared chunks, and a
  manifest into one ignored Django static directory.
- [x] Replace all Tailwind/esbuild/watcher scripts with one build/watch surface.
- [x] Prove Tailwind output is declaration-, cascade-, and computed-style
  equivalent before migrating other styles.

### Django integration

- [x] Add typed manifest parsing and `vite_styles`, `vite_preload`, and
  `vite_script` template tags.
- [x] Cover production caching/failure, DEBUG refresh/fallback, recursive
  preload resolution, deduplication, path validation, and static-storage URLs.
- [x] Replace first-party stylesheet and script references while retaining
  external vendors and exact order.
- [x] Preserve all dark-scheme metadata and public/private `.dark` behavior.

### First-party source migration

- [x] Move public/private shell behavior into explicit Vite entries.
- [x] Convert shared form and security helpers to imported ES modules.
- [x] Convert public auth, dashboard, experiment, fleet, permission, tools,
  tag/list, landmark, and map behavior to route controllers.
- [x] Replace application globals and inline handlers with direct/delegated
  listeners; keep only documented third-party and Django-generated globals.
- [x] Replace executable template contexts with inert JSON/data attributes.
- [x] Extract static inline CSS into ordered global or route-owned entries.
- [x] Remove all direct references to raw first-party asset sources.

### Orchestration and documentation

- [x] Update Compose, Railpack, Railway, CI, pre-commit, and legacy deployment
  hooks so Vite builds during image construction and Django remains the server.
- [x] Update AGENTS, Node/Tailwind docs, map-viewer architecture/testing docs,
  prior migration records, and the correction lesson.
- [x] Re-record Git state and prove the starting index is unchanged.

### Verification

- [x] Run three deterministic clean production builds and inventory outputs.
- [x] Run JavaScript lint/tests, Vite contracts, Django template validation,
  focused pytest, full pytest, and full `prek`.
- [x] Prove watcher invalidation for CSS, Tailwind sources, JS/TS dependencies,
  controller changes, deletion, and unrelated-route isolation.
- [x] Verify Node 22.12+ and Node 24 clean installs and install approvals.
- [ ] Verify `collectstatic`, local RustFS module CORS/MIME, Compose, Railpack,
  Railway lifecycle, and served manifest hashes.
- [ ] Run deterministic Chromium, Firefox, and WebKit baseline/candidate parity
  for every migrated controller family and required interaction/state matrix.
- [ ] Record size, request graph, parse/init, and style-recalculation metrics.
- [ ] Leave completion unchecked for every unavailable or unexplained gate.

## Area ledger

| Area | Baseline evidence | Candidate evidence | Primary risk | Falsifying test | Conclusion / fix / proof |
| --- | --- | --- | --- | --- | --- |
| Git/index | Cached/index hashes above | Same cached/index hashes; branch and HEAD unchanged | Accidentally staging or rewriting approved work | Compare cached diff and `git ls-files -s` hashes | Proven unchanged after implementation |
| Tailwind | One CLI-built `app.css` from `tailwind_css/style.css` | 1,479 rules in both outputs; normalized declaration inventory has no difference | Layer/order/token drift | Semantic inventory plus live computed/pixel parity | Equivalent; Vite only normalizes media syntax and duplicate vendor prefixes |
| Public shell | Tailwind, public custom CSS, vendors, classic `main.js` | Vite shell/controller plus parser-time particle snapshot | Font/cascade/animation drift | Public route matrix | Final 30-case matrix is exact after documented engine/environment normalizers |
| Private shell | Tailwind, private custom CSS, responsive inline CSS, XSS global | Shared bootstrap plus lazy route controllers | Private reference changes | Private route matrix | Candidate authenticated three-engine smoke passed; baseline parity remains incomplete |
| GIS/map | Public/private map entry bundles and external Mapbox | Lazy public/private controllers and shared Vite chunks | Shared graph leakage or changed initialization | Public/private map behavior and network graph | Unit/graph tests pass; full live role matrix remains incomplete |
| Forms/controllers | Direct classic helpers plus inline initializers | Inert JSON declarations and 30 lazy controllers | Lost globals, order, or error behavior | Per-controller unit and live form cases | 49 JS test files / 927 tests pass |
| Route styles | Direct CSS and 46 templates with style blocks | 47 ordered Vite style entries | Reordering or selector leakage | Ordered inventory and pixel parity | Contract inventory passes; public parity focused cases exact |
| Manifest/Django | Fixed static paths | Mtime-refreshed DEBUG and cached production resolver through static storage | Stale/missing manifest or broken S3 URL | Template-tag unit/integration tests | Unit/failure/deduplication/stale-file cases pass |
| Watch mode | Polling Tailwind plus three esbuild watchers | One Vite disk watcher | Missed deletion/import/source rebuild | Isolated mutation matrix | Initial build and CSS/Tailwind/shared/controller/isolation cases pass |
| Deployment | Assets built in Railway predeploy | Railpack image build owns assets; predeploy only migrates/collects | Manifest absent from runtime image | Railpack image and exact lifecycle test | Files/contracts updated; local image construction unavailable |
| Vendors | Local DEBUG and CDN production globals | Vendor elements and relative order preserved | Execution-order/CORS changes | Rendered order and browser console/network checks | Three-engine public/private smoke has no console, network, or MIME errors |
| Security | Escaping helpers and some inline/global handlers | Imported helpers, structured contexts, delegated map actions | XSS regression during event refactor | Sink audit and adversarial payload tests | Existing and added XSS/delegation tests pass; full role matrix remains incomplete |

### Baseline production artifacts

| Artifact | SHA-256 | Bytes | gzip | brotli |
| --- | --- | ---: | ---: | ---: |
| Unified Tailwind CSS | `4e17b71b05a5bfae593a57a3689fb749c2e516b57bc97019dd4eeb4190357e74` | 146,168 | 22,966 | 18,125 |
| Private map JavaScript | `9d15c1ba69489189125035fd9923e4d0fb940bca867fdc8d9387675b062c2b3b` | 406,572 | 80,082 | 62,683 |
| Landmark details JavaScript | `31123cd6af27af93dbeee26860bcac6a5e3a502048ab7a9b35935eac7be97a85` | 39,448 | 11,389 | 10,011 |
| Public GIS JavaScript | `d63ab067adc99866e05f459500c5fbb582e323d3151329dbef288c82baef9211` | 80,788 | 22,161 | 18,962 |

The isolated production build completed successfully with Tailwind 4.3.1 and
the three current esbuild entry outputs. These artifacts—not the ignored files
in the working tree—are the comparison baseline.

### Final candidate asset graph

| Route graph | Files | Bytes | gzip | brotli |
| --- | ---: | ---: | ---: | ---: |
| Bootstrap | 2 | 8,498 | 2,719 | 2,411 |
| Public shell | 3 | 13,804 | 4,532 | 3,998 |
| Private dashboard | 4 | 17,755 | 6,577 | 5,833 |
| Public GIS | 8 | 95,428 | 28,206 | 24,585 |
| Private map | 8 | 423,954 | 87,040 | 70,339 |
| Tailwind CSS | 1 | 146,534 | 22,950 | 18,093 |

The Tailwind artifact is 0.25% larger raw and smaller under gzip/brotli than
the CLI baseline. The private-map graph is under the 10% raw threshold. The
public-GIS graph includes the shared bootstrap/public shell and is 7.0% larger
raw but 15.1% larger under gzip than the former GIS bundle plus public
`main.js`; the acceptance condition also requires a greater-than-1-ms median
runtime regression, which has not been reproduced or cleared, so the
performance gate remains open.

## Review

Not complete. The implementation is present, but the acceptance contract keeps
this task open until the unavailable deployment and full authenticated/map
browser matrices are reproduced.

Implemented findings and repairs:

- Vite 8.1.0 and `@tailwindcss/vite` 4.3.1 now own one registry, graph,
  manifest, output root, disk watcher, and production command. Tailwind CLI,
  direct esbuild, concurrent watchers, and the polling watcher were removed.
- All 98 authored JavaScript sources and every authored stylesheet are either a
  registry entry or a transitive module. Two unreferenced legacy stylesheets
  were proven dead and removed.
- Django resolves hashed entries recursively through static storage, reloads by
  manifest mtime in DEBUG, caches in production, and rejects malformed,
  duplicate, path-escaping, or stale/missing assets.
- Every static template style block and executable application script/handler
  was replaced by an ordered style entry or inert controller context. Vendor
  globals and Django's generated URL module remain external by contract.
- Vite's lazy controller timing initially changed the public particle canvas's
  parser-time dimensions. The bootstrap now snapshots those dimensions before
  the lazy import and the controller consumes them only for its first sizing;
  real resize events continue to use live measurements.
- The parity harness uses separate browser processes and cache contexts,
  normalizes only the required isolated-server host text, and masks only
  continuously animated particle pixels while still comparing their boxes and
  computed styles.

Reproduced verification so far:

- Node 22.22.2 and Node 24.18.0 clean installs and production builds pass;
  the only install script is optional `fsevents` and `npm audit` reports zero.
- Three final clean builds completed in 293 ms, 276 ms, and 247 ms with the
  identical aggregate artifact hash
  `44d5f6499aaecf12a63251e518507164032b76c222447a12c5e1b045f25b27a6`.
- The isolated Vite watcher passes CSS edit/deletion, Tailwind source edit,
  shared module, route controller, and unrelated-route isolation cases.
- Candidate Chromium/Firefox/WebKit smoke passes 30 public/auth/Ariane cases
  and six authenticated dashboard cases with dark scheme, single controller
  initialization, clean console/network, and valid module MIME.
- The final isolated baseline/candidate public matrix passes all 30 cases with
  zero structural, computed-style, geometry, or unnormalized pixel differences
  across Chromium, Firefox, and WebKit at 360px/DPR 2 and 1440px/DPR 1.
- Production-shaped `collectstatic` and an ephemeral RustFS bucket pass module
  MIME, public cache headers, and configured CORS-origin checks.
- Full pytest reached 3,805 passed, 156 skipped, and 31 failures; all 31 require
  the unavailable local GitLab service on port 9080 and are unrelated to the
  asset pipeline. Focused migrated Django suites pass 248 tests; all 49 JS test
  files and 927 tests pass. Template validation, Django checks, `npm run
  pre-commit`, full `prek`, lint, and both Git diff checks pass.
- Final cached diff and index hashes exactly match the recorded starting values;
  the branch remains `dsf` at `c1977452ee0e6dc259ea893c683ca47a56cef662`.

Browser evidence normalizes only reproducible environment/engine behavior:

- isolated servers render different ports in the public footer, so that text is
  normalized to `parity.test`;
- continuously animated particle pixels are masked, but canvas structure,
  computed style, and stable post-load resize geometry are compared;
- WebKit candidate-self controls reproduce up to one 8-bit channel of gradient
  interpolation variance between processes, so only per-channel deltas of one
  are normalized and their raw count is retained.

Remaining gates: final deterministic build/hash and repository-gate reruns,
the complete baseline/candidate authenticated role/map/interaction matrix,
Dark Reader, production S3/CloudFront, Compose/Railpack image construction,
and Railway's deployed lifecycle. None is silently treated as passing.
