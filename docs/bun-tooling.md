# Bun and Vite Tooling

## Intent

SpeleoDB has one root JavaScript workspace and one first-party asset graph. Bun
owns dependency installation, package-script launching, and JavaScript
execution. Vite compiles Tailwind, route CSS, application ES modules, and shared
chunks; Django remains the only HTML and static-file server. The repository does
not run Vite's development server, proxy, HMR client, or HTML transformer.

The exact Bun version is declared once in `.bun-version` and mirrored by
`package.json`'s `packageManager` as `bun@<version>` and `engines.bun` as the
exact version. Containers, GitHub Actions, and Railpack read that file. Pinning
the runtime and package manager keeps lockfile parsing, resolution, lifecycle
policy, and frozen installs consistent across environments.

`bunfig.toml` sets `[run] bun = true` so package executables and their children
use Bun. Direct tool subprocesses also launch through the Bun executable.
Containers, GitHub Actions, and Railpack provision that same runtime from the
version file. Runtime contract tests assert the actual process runtime rather
than accepting a package-manager command as proof of execution ownership.

Direct dependency specifications live in `package.json`; exact resolutions live
in `bun.lock`. The text lockfile uses JSONC, including trailing commas, so
readers must use a JSONC parser. Tooling contract tests invoke Bun's native
`Bun.JSONC.parse` through a fixed subprocess. Workspace requirements must agree
with the manifest; registry package tuples retain version identities and archive
integrity. Bundled package entries inherit integrity from their containing
archive rather than carrying an independent checksum. Audit dependency edges,
optional platform variants, and nested versions when changing the graph.

Archive identity preservation does not imply identical platform metadata. The
pinned Bun importer maps unsupported CPU targets `loong64`, `mips64el`,
`riscv64`, and `wasm32` to `none`, maps unsupported OS targets `netbsd` and
`openharmony` to `none`, and omits the source lock's `libc` field. Those
archives and their checksums remain in the graph, but the converted filters
cannot prove installation parity on every upstream platform. Verify native
package loading on the supported container and developer platforms; keep these
representation limits explicit when comparing locks.

The manifest explicitly trusts only `esbuild` and `fsevents` dependency
lifecycle scripts through `trustedDependencies`. This includes the optional
macOS package even when a Linux install does not execute it. Review changes to
this list; do not broaden trust to all packages or suppress scripts required for
native tools. The hoisted linker preserves the existing `node_modules` layout
used by tools and test subprocesses.

## Asset graph

`frontend_common/entries.json` is the committed logical-entry registry. Vite
uses it as its complete input set and Django uses the same names when rendering
manifest-backed tags. Entries preserve route boundaries: one Tailwind sheet,
separate public/private shell styles, route/modal/map styles, one small
bootstrap, and lazy route controllers. Shared imports become shared chunks.

Production writes hashed files and `.vite/manifest.json` under
`speleodb/common/static/speleodb/vite/`. Development publishes immutable
`assets/dev/<session>/<generation>/` trees with source maps. The complete
manifest is atomically replaced after all referenced output exists. Django
serves those files and a development-only client reloads after publication.

All SpeleoDB-authored CSS/JS belongs in the graph as an entry, transitive
module, test, or intentionally removed source. Templates load it with
`vite_styles`, `vite_preload`, and `vite_script`. Vendored/CDN libraries and
Django-generated `url_reverse.js` remain outside Vite.

## Commands

- `test -s bun.lock && bun install --frozen-lockfile`: install the committed
  graph, rejecting a missing or empty lockfile before the installer can resolve
  a replacement. A successful install must leave the lockfile unchanged.
- `bun run build:clean`: remove Vite and obsolete Tailwind/esbuild output.
- `bun run build:assets`: strict checking and both source audits, then Vite
  production output.
- `bun run build`: check types and both audits before cleaning and building
  assets.
- `bun run dev`: supervises the Vite disk watcher and TypeScript semantic
  watcher.
- `bun run start`: alias for `bun run dev`.
- `bun run pre-commit`: the same clean production build contract.
- `bun run test:assets-watch`: isolated watcher invalidation matrix.
- `bun run lint:frontend` and `bun run test:frontend`: source quality gates.
- `bun run typecheck`: strict checking across three environments.
- `bun run typecheck:development`: unit/browser tests, upload subprocesses,
  tools and Railway authoring.
- `bun run test:browser`: the existing Playwright browser suite.

`bun run` executes the existing Vite, Vitest/jsdom, Playwright, lint, and
typecheck scripts with Bun. The watcher verifier and browser-upload subprocess
use the same runtime. Retain the existing Vitest configuration and argument
forwarding; `bun test` selects a different test runner. Package executables used
outside scripts run through `bunx --bun`. Use `bun outdated` to inspect releases
and `bun update --interactive` to select updates. `bun run update` and
`make update` run `bun update --latest` for all dependencies, followed by the
Browserslist data refresh. See [Dependency Updates](dependency-updates.md).

The Prettier hook uses prek's `bun` language for installation and an explicit
`bun run --bun prettier` entry for execution. Selecting an installation language
alone does not override the upstream executable's shebang. Validate hook runtime
selection as well as package-script execution.

The watcher test mirrors sources under the operating-system temporary directory
and reuses the installed dependency tree. It proves imported CSS
change/deletion, Tailwind source additions, shared-module invalidation,
route-controller invalidation, unrelated-route output stability, failed-build
publication, retained old assets and worker generation ownership.

The migration-era Tailwind Vite plugin accumulated discovered utility candidates
during one watch process. Treat a deleted template class as potentially retained
until restart; the watcher contract separately covers imported CSS deletion.
Final evidence must always stop the watcher, run `bun run build`, and verify the
served manifest hash. A running watcher is development convenience, never
release evidence.

## Django and deployment

The Django manifest reader reloads by manifest mtime in DEBUG and caches in
production. Every template render shares one snapshot across asset tags and
includes, so a rebuild cannot mix generations within a page. Missing, malformed,
unsafe, duplicate, or wrong-type entries fail loudly. DEBUG/test may fall back
to registry-derived stable names before the first watcher build. URLs pass
through Django static storage, preserving local serving and S3/CloudFront
behavior.

Railpack retains the Python provider and uses Mise to activate Bun from
`.bun-version`. It checks the runtime version, performs the guarded frozen
install, and runs `bun run build`. Tool versions are owned by the repository
rather than duplicated in Railpack's package map. The runtime retains generated
assets and manifest but not `node_modules`. Railway pre-deploy runs migrations,
`install_background_schedules`, and `collectstatic`. Asset compilation belongs
to the image build because pre-deploy filesystem changes are not persisted. SPA
serving is disabled and Gunicorn/Django remains the start command.

The alternative `bin/post_compile` entrypoint also propagates installation and
asset-build failures before static collection or compression. Its subprocess
tests replace Bun and Python with local command recorders, so checking failure
propagation never publishes assets or invokes deployment services.

For an intentional dependency refresh, resolve from the manifest and existing
text lockfile in an empty external directory, independently of `node_modules`.
Use the workflow in [Dependency Updates](dependency-updates.md), then verify a
guarded frozen install without rewriting the lock. A package-manager transition
preserves the direct specifications, exact package/version/integrity identities,
and resolved dependency edges, including optional platform variants, except for
explicitly authorized compatibility changes. Do not run general
dependency-update commands during a transition. Different physical hoisting does
not authorize changing a package version.

Verification covers the full Vitest suite, JavaScript lint, Railway
typechecking, the isolated watcher, a clean production build, and the browser
cases relevant to the change. Tooling contract tests check the shared version
authorities, frozen-install commands, script trust, lock metadata, and
deployment automation. They also assert Bun execution for scripts and spawned
tools, so a compatible API surface cannot conceal a different runtime. Run the
migrated JavaScript and TypeScript checks inside the existing application
container. Preserve historical browser timing and memory limitations when
reporting results. The package manager adds no application runtime work; native
tool loading, output coherence, and watcher invalidation prove the build remains
usable without changing frontend behavior.

Deployment verification also checks `collectstatic` and production module
MIME/CORS behavior. Full dependency refreshes retain the broader Python and hook
gates described in [Dependency Updates](dependency-updates.md).

## Monorepo command scope

Here, root JavaScript commands mean the web application's `apps/web` root. Run
installs and tests in the already-running application container at `/app`. That
standalone bind mount prevents Bun's ancestor-workspace discovery from selecting
the enclosing monorepo and its separate lockfile. Changing directories to
`apps/web` on the host alone does not establish this isolation. The named
`/app/node_modules` volume also keeps Linux native packages separate from the
host's architecture. For a web-scoped change, run the web commands and prek
hooks; enclosing aggregate commands can enter unrelated applications. Do not
start a new stack for verification.

## Reference searches

Case-insensitive searches for obsolete tooling commands need semantic review.
DOM APIs, JSON tree nodes, pytest identifiers, Celery worker names, product
anode fields, vendor source, CDN URLs, source maps, and checksums are not
migration targets. Parent-monorepo helper paths retain their actual names
because the web application does not own those files. Report the remaining
categories with the search result rather than claiming zero literal matches or
modifying unrelated interfaces and artifacts.

Native TypeScript 7 checks the full source graph with `allowJs: false`. A
TypeScript 6 compiler API alias supports typed ESLint. Source and template
audits enforce zero authored JavaScript and executable template expressions,
with exact vendor/generated exceptions. See
[TypeScript architecture](typescript-architecture.md) for environment
boundaries, compiler compatibility and build enforcement.
