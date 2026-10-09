# Dependency Updates

## Intent

Dependency refreshes are repository-wide compatibility changes, not mechanical
version edits. A refresh must produce one coherent Python, JavaScript, CI, and
container contract while preserving application behavior and reproducible
installs. Open Dependabot PRs provide the initial candidate set; the local
resolvers decide which combined graph is actually valid.

## Ownership and update sequence

Python direct requirements and extras are owned by `pyproject.toml`, with the
complete cross-extra graph in `uv.lock`. JavaScript tooling is one root
workspace owned by `package.json` and the JSONC text lockfile `bun.lock`.
`.bun-version` owns the exact runtime and package-manager release, mirrored by
the manifest's `packageManager` and `engines.bun` values. Local containers,
GitHub Actions, and Railpack read that file. GitHub Actions own other CI tool
bootstrap versions, and `compose/Dockerfile` owns the local Python image. Cargo
workflows do not apply unless their manifests exist in the tree.

Fetch the authoritative list of open Dependabot PRs targeting `dev`, merge all
of their heads locally, and then consolidate overlaps in the manifests. Inspect
JavaScript candidates with `bun outdated`, then use the isolated Bun refresh
below for authorized major upgrades. Run `uv lock --upgrade` for the complete
Python graph. Finally inspect `uv tree --outdated --depth 1`; an older direct
dependency is acceptable only when the resolver proves a concrete upstream
constraint, which must be logged in `AGENTS.md` in the form
`Can't update A until X is satisfied`.

Run `prek update` and review all hook changes as part of the same refresh. Hooks
that wrap project tools, including ruff and djLint, must remain aligned with the
versions installed from `pyproject.toml`; otherwise local direct runs and
commit-time validation enforce different rule sets.

## Lockfile invariants

### Relocking the standalone web checkout

Inside the monorepo, run `bun run lock` from `apps/web` after editing
`package.json`. Use `bun run lock --upgrade` to refresh all direct and
transitive resolutions within the existing manifest constraints, like
`uv lock --upgrade`. Exact versions, Git SHAs, overrides and semver ranges
remain authoritative; this command never changes `package.json` or opts into
major upgrades outside its ranges. Ordinary relocking retains already satisfied
locked versions.

The web entrypoint delegates to the monorepo's `utilities/bun-lock/lock.mjs`,
shared with mobile and the map packages. It also works from `/app` in the
monorepo container, where the helper is available under `/workspace`. Standalone
clones do not include this convenience helper; use
`bun install --lockfile-only --ignore-scripts` there. Existing standalone CI and
install commands remain independent of the helper.

The helper requires the exact `.bun-version` runtime, copies only resolver
inputs into an external temporary directory, and atomically publishes only
`bun.lock` after success. It rejects temporary directories under another
package, unsupported local/workspace dependencies and patches, unknown flags,
and inputs edited during resolution. An upgrade starts without the previous lock
and bypasses cached registry metadata so transitive versions are refreshed too.
Resolver failure leaves the original lock untouched.

It does not install `node_modules`, run lifecycle scripts, or refresh the
monorepo integration locks. Registry and Git resolution can still access the
network and Bun's shared cache. Optional `.npmrc` and Bun configuration are
preserved; file-based certificate paths must be absolute. Temporary copies are
removed on normal completion and exceptions. See the monorepo utility README for
scope and verification details. The web regression tests cover argument,
working-directory and failure forwarding through its entrypoint. There is no
application runtime cost.

### Dependency upgrades

`bun run update` (also exposed as `make update`) runs `bun update --latest` for
all dependencies, including major upgrades, then refreshes Browserslist data.
Review peer constraints and resolver warnings before accepting the refreshed
graph.

Resolve the Bun lockfile independently of `node_modules`. Copy the combined
`package.json`, `bun.lock`, `bunfig.toml`, and `.bun-version` into an empty
operating-system temporary directory outside every checkout. Use that directory
as the actual working directory and the Bun release selected by `.bun-version`;
run `bun update --latest '*' --lockfile-only --ignore-scripts` once to refresh
the combined graph. Quote the pattern so the shell cannot expand it. Validate
the resulting manifest and lockfile before copying both back. This is an
intentional dependency-update workflow, not the workflow for a package-manager
transition that must preserve existing versions.

The generated text lockfile must meet all of these conditions:

- its JSONC workspace requirements agree with `package.json`;
- package identities and dependency references contain no temporary or host
  paths, and all resolved dependency edges identify existing locked packages;
- registry package tuples retain exact names, versions, and archive checksums;
  bundled entries inherit their parent archive's integrity and must not acquire
  fabricated independent checksums;
- optional platform archive identities and required nested versions remain
  represented, subject to the platform-filter limits below;
- explicit `trustedDependencies` approvals cover only reviewed lifecycle
  scripts; the current approvals are `esbuild` and `fsevents`;
- `test -s bun.lock && bun install --frozen-lockfile` succeeds from `/app` in
  the existing application container and does not rewrite the committed graph.

The nonempty-lock guard is required in startup, CI, and image builds because an
installer must fail when the authoritative lock is missing. Keep the hoisted
linker configured for the existing tool and subprocess layout. Inspect
`bun pm untrusted` after a clean install and review any newly blocked scripts.
Compare lock graphs by package identity and resolved edges, rather than treating
physical hoisting differences as version changes.

Do not require byte-for-byte platform-field equality when comparing imported
locks. The pinned Bun importer uses `none` for CPU targets `loong64`,
`mips64el`, `riscv64`, and `wasm32`, and OS targets `netbsd` and `openharmony`;
it also omits the source lock's `libc` field. Preserve all archive identities,
checksums, and resolved dependency/peer edges despite those representation
changes. Record the limits and verify native dependency loading on supported
Linux/container and developer platforms. Unchanged archive identities alone do
not establish successful installation on every upstream platform.

Dependabot uses the `bun` ecosystem for this workspace and updates `bun.lock`.
The Browserslist workflow uses `bunx --bun update-browserslist-db@latest` and
commits the text lockfile. Keep its existing branch, schedule, and review
policy.

`uv.lock` is regenerated with all project extras in one resolution. Direct pins
that make the combined graph unsatisfiable are reverted to the newest compatible
release and recorded as blockers; unrelated constraints are not weakened merely
to make a candidate version resolve.

## Compatibility and performance

The Bun `packageManager` and `engines.bun` mirrors must match `.bun-version`.
Every build environment reads that file rather than carrying a second version.
Bun owns installation and execution of Vite, Vitest, Playwright, and tool
subprocesses. Keep `[run] bun = true` in `bunfig.toml` and use `bunx --bun` for
executables launched outside package scripts. Major updates to test
environments, compilers, framework packages, serializers, database clients, or
geospatial/media bindings require the same relevant-suite evidence as a source
change. Dependency updates must not add runtime queries, frontend work, or new
services; any performance change should come only from the selected upstream
implementations.

The DRF 3.18 typing contract accurately models parsed request data as either a
JSON object or array. Object-only handlers narrow that shape through
`require_mapping_request_data()` before indexing, mutation, or permission
parsing. The shared guard returns object data unchanged and raises DRF
`ParseError` for arrays, producing a deterministic HTTP 400 instead of an
attribute/indexing 500. Read-only callers avoid an unnecessary allocation;
callers that mutate the payload explicitly copy it so the mutation boundary is
visible and parsed request state remains unchanged. Serializer-owned endpoints
continue passing parsed data directly to their serializers so each serializer
retains shape validation.

## Verification

After clean JavaScript and Python installs, run the production Vite build,
JavaScript lint and unit tests, the full Django/Python test suite, and
`prek run -a`. Container-build validation proves the deployment toolchain and
native wheels still install. Review the final manifest and lockfile diff for
unrelated packages, nonportable paths, missing checksums, and unapproved install
scripts before creating the single `[Dependency Update]` commit.

Tests should assert graph properties rather than duplicate installed release
numbers from manifests: package presence, manifest/lock agreement, portable
identities, dependency edges, registry integrity, and install-script approvals.
Do not pin package releases, lockfile format numbers, or versioned install keys
in unit tests merely to repeat the resolver output. Product formats, protocol
versions, and intentionally frozen compatibility fixtures remain valid version
contracts.
