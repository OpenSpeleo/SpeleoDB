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
workspace owned by `package.json` and `package-lock.json`. GitHub Actions own CI
tool bootstrap versions, and `compose/Dockerfile` owns the local Python image.
Cargo and Bun workflows do not apply unless their manifests exist in the tree.

Fetch the authoritative list of open Dependabot PRs targeting `dev`, merge all
of their heads locally, and then consolidate overlaps in the manifests. Run
`npx --yes npm-check-updates -u --peer` for direct JavaScript releases and
`uv lock --upgrade` for the complete Python graph. Finally inspect
`uv tree --outdated --depth 1`; an older direct dependency is acceptable only
when the resolver proves a concrete upstream constraint, which must be logged
in `AGENTS.md` in the form `Can't update A until X is satisfied`.

Run `prek update` and review all hook changes as part of the same refresh.
Hooks that wrap project tools, including ruff and djLint, must remain aligned
with the versions installed from `pyproject.toml`; otherwise local direct runs
and commit-time validation enforce different rule sets.

## Lockfile invariants

Generate the npm lockfile without consulting `node_modules` or its hidden
lockfile. A safe process copies the root manifest to an empty temporary
directory, changes the process working directory to that directory, generates
the lockfile, validates it, and only then replaces the committed lockfile. Do
not use npm's `--prefix` for this process: npm can encode the temporary prefix
into the root metadata and package keys.

The generated npm lockfile must meet all of these conditions:

- every package key is either the empty root key or starts with
  `node_modules/`;
- root dependencies exactly match `package.json`;
- every registry-backed node retains its `resolved` URL and `integrity`
  checksum;
- a clean install does not rewrite the committed graph.

`uv.lock` is regenerated with all project extras in one resolution. Direct
pins that make the combined graph unsatisfiable are reverted to the newest
compatible release and recorded as blockers; unrelated constraints are not
weakened merely to make a candidate version resolve.

## Compatibility and performance

The Node engine range follows the intersection required by the installed
tooling graph and the Node releases exercised by CI/deployment. Major updates to
test environments, compilers, framework packages, serializers, database
clients, or geospatial/media bindings require the same full-suite evidence as a
source change. Dependency updates must not add runtime queries, frontend work,
or new services; any performance change should come only from the selected
upstream implementations.

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
