# Single Private-Reference Tailwind Bundle

> Superseded as the production asset architecture by
> `tasks/todos/vite-asset-pipeline.md`. The private-reference Tailwind source
> remains authoritative, but Vite now owns compilation, manifest output, and
> delivery alongside all first-party CSS and JavaScript.

## Goal

Replace the staged two-output CSS-native migration with one neutral Tailwind
build and one generated product asset. The staged private entrypoint is the
immutable visual/configuration reference. Public pages adopt its tokens through
durable `site-*` components without changing private rendering.

## Checklist

- [x] Freeze Git state and clean public/private CSS baselines.
- [x] Add one neutral entrypoint and generated output.
- [x] Namespace public-only components and update every consumer.
- [x] Replace dual build/watch/pre-commit interfaces with one pipeline.
- [x] Point every Tailwind-owning document at the neutral asset exactly once.
- [x] Rewrite compiler, source, component, script, and rendered contracts.
- [x] Prove the private reference remains structurally unchanged and prove zero
      visual difference in the deterministic cross-engine fixture matrix.
- [x] Verify typography is the only public computed-style difference in the
      deterministic cross-engine fixture matrix.
- [x] Run repository, Node-version, watcher, browser, Docker, and Railway gates.
- [x] Update architecture, tooling, audit, agent guidance, and lessons.
- [ ] Reproduce the complete authenticated live-Django route/role/interaction
      matrix required for final completion.

## Baseline

- Branch: `dsf`; existing index preserved and all work for this correction stays
  unstaged.
- Public unminified: `f46eb314…`, 109,921 bytes, 3,853 lines.
- Private unminified: `5a5b81df…`, 137,320 bytes, 4,926 lines.
- Public minified: `6e4b5ec0…`, 86,562 bytes.
- Private minified: `a026197f…`, 110,774 bytes.
- Immutable private source hashes:
  - entrypoint: `44daabdb…`;
  - components: `29990d20…`;
  - flatpickr: `876a74a8…`.

## Risk and Regression Ledger

| Area                 | Contract / baseline                                  | Risk                                                                     | Falsifying test                                         | Conclusion / fix / proof                                                                                                                                                                                                                                                                                                                                                                       |
| -------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Git process          | Staged migration at the checkpoint above             | Mixing the approved index with corrective work                           | Compare cached and worktree state at every checkpoint   | Branch remains `dsf`; no index-mutating command was run; `git diff --cached --check` passes and every repair remains visibly separate in the worktree.                                                                                                                                                                                                                                         |
| Private UI           | Frozen private CSS and live routes                   | Union candidates or public CSS change private cascade                    | Private-rule subsequence plus computed/pixel comparison | All three private source hashes remain exact. The compiler contract proves the private rule sequence/declarations are retained. The final real-Django matrix covered dashboard, map, and Git browser in Chromium, Firefox, and WebKit at 360/767/768/769/1440 px and DPR 1/2 with zero unexplained computed or pixel differences.                                                              |
| Public UI            | Frozen public CSS and route composition              | Renamed components lose behavior or private tokens cause unrelated drift | Computed allowlist and public interaction/pixel matrix  | Public components use `site-*`. The real-Django matrix covered home, login, Ariane, and GIS across the same 30 engine/viewport/DPR combinations. A live comparison found and fixed the old public `shadow-sm` geometry as `site-shadow-sm-purple-25`; only approved typography/reflow and the intentional GIS shell/header convergence remain. Wider role and animation coverage remains open. |
| GIS composition      | Public + private Tailwind currently load in sequence | Removing the second link changes map/header/modal cascade                | Rendered order assertions and live public GIS states    | Rendered tests prove one neutral link and preserve custom/modal/map order. Live comparison proved GIS controls retain private `.btn`, the public shell/header is consistently public, and the welcome modal retains its old effective `p-6` spacing. The obsolete duplicate link is gone.                                                                                                      |
| Sources              | Two explicit source sets                             | A union build omits runtime strings or scans unsupported trees           | Mirrored compiler sentinels                             | The 12-test compiler contract proves union sentinels, exclusions, plugin ownership, namespace isolation, and private-rule retention.                                                                                                                                                                                                                                                           |
| Build/watch          | Six scripts and two compiler processes               | Stale output, missed imported CSS, or old interface survives             | Script contract and isolated watcher mutation test      | One build/dev/pre-commit interface remains. The isolated polling watcher rebuilt shared and source mutations and removed a deleted `z-[987]` candidate.                                                                                                                                                                                                                                        |
| Theme declaration    | Four owned dark roots and Dark Reader lock           | Public `.dark` activates private-only variants                           | Rendered root and browser extension checks              | Five rendered tests prove metadata/order and no public `.dark`. Pinned Dark Reader 4.9.125 injected nine control styles and zero styles into the locked site; all engines report `color-scheme: dark`.                                                                                                                                                                                         |
| Delivery/performance | Two minified files total 197,336 bytes               | One cold bundle grows per-route CSS/style cost                           | Minified/gzip/brotli and forced-style measurements      | Three final clean builds produced `4e17b71b…` at 146,168 bytes. Gzip is 22,974 bytes and Brotli is 18,125 bytes, respectively 29.8% and 32.2% below the combined predecessors. Final median style-pass deltas were +0.310 ms public and +0.095 ms private, below the 1 ms per-pass guard.                                                                                                      |

## Review

The single-bundle implementation and all locally reproducible structural gates
are complete. Focused and full verification passed:

- Tailwind contract: 12/12; JavaScript: 45 files and 920 tests; lint: clean.
- Django: 5 rendered theme tests, 123 focused tests, and the full suite at 3,824
  passed / 156 skipped; Ruff, mypy (589 files), template validation under
  CI-shaped settings, and full `prek`: clean.
- Node 22 and Node 24 clean installs/builds/lint/tests: clean, zero npm
  vulnerabilities. Docker repeated the Node 22 build/lint/920-test gate.
- Railway's exact install/build/migrate/collectstatic sequence passed in the
  application image against a disposable PostgreSQL 16 service; 776 static files
  were collected.
- Three clean minified builds were byte-identical. The isolated watcher,
  Chromium/Firefox/WebKit fixture matrices, DPR 1/2, Dark Reader lock, and
  style-recalculation measurements passed as recorded above.
- Two real Django servers rendered the staged two-bundle index and unified
  candidate against one deterministic PostgreSQL database, authenticated
  session, project, and GIS view. The final seven-route matrix passed 210/210
  cases; the two Git actions passed 360/360 state captures across default,
  hover, focus, focus-visible, active, and touch-hover.
- Browser evidence uses no pixel masks. Structured normalizers cover only
  renamed `site-*` identities, old/new asset paths, per-origin CSRF values,
  approved public typography/reflow, the intentional GIS shell/header, and
  WebKit's nondeterministic closed-`OPTION` serialization. That WebKit case had
  identical owning controls and zero differing pixels.
- Live evidence found two public regressions before the final pass: the private
  `shadow-sm` token changed four marketing-card shadows, and removing the later
  GIS bundle activated responsive welcome-modal padding that previously never
  won the cascade. Both now have focused compiler assertions and exact live
  regression proof.
- `git diff --check` and `git diff --cached --check` pass. The immutable private
  hashes are `44daabdb…`, `29990d20…`, and `876a74a8…`.

The completion gate deliberately remains open: the deterministic real-server run
used one authenticated admin fixture and seven representative routes; it did not
reproduce every requested role, permission state, application route, animation,
and public interaction. The implementation, deployment gates, and the recorded
private/public/Git matrices are complete, but they are not a substitute for that
exhaustive product-wide matrix.
