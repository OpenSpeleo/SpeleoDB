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

Archive identity does not establish platform installability. The committed lock
includes optional archives whose CPU or OS filter is `none`; retaining those
archives and checksums does not make them selectable on their upstream targets.
Native dependency loading must be verified on the supported container and
developer platforms. Lock comparisons must distinguish preserved package
identities from platform-filter representation and actual native-tool support.

The manifest explicitly trusts only `esbuild` and `fsevents` dependency
lifecycle scripts through `trustedDependencies`. This includes the optional
macOS package even when a Linux install does not execute it. Bun records only
approvals for packages present in the resolved graph in `bun.lock`; an optional
peer such as `esbuild` may therefore remain approved in the manifest without a
lockfile entry. Review changes to this list; do not broaden trust to all
packages or suppress scripts required for native tools. The hoisted linker
preserves the existing `node_modules` layout used by tools and test
subprocesses.

## Asset graph

`frontend_common/entries.json` is the committed logical-entry registry. Vite
uses it as its complete input set and Django uses the same names when rendering
manifest-backed tags. Entries preserve route boundaries: one Tailwind sheet,
separate public/private shell styles, route/modal/map styles, one small
bootstrap, and lazy route controllers. Shared imports become shared chunks.

Explicit builds write hashed files and `.vite/manifest.json` directly under
`speleodb/common/static/speleodb/vite/`. Production output is minified; an
explicit development-mode build includes source maps. Django serves the compiled
files after the user refreshes the browser. The local Django launcher starts the
`dev` watcher, which rebuilds on save; page refreshes stay manual, with no
reload client or generation polling.

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
- `bun run dev`: initial type/ownership checks, then automatic development asset
  rebuilds; browser refresh stays manual.
- `bun run start`: finite alias for `bun run build`.
- `bun run pre-commit`: the same clean production build contract.
- `bun run lint:frontend` and `bun run test:frontend`: source quality gates.
- `bun run typecheck`: strict checking across three environments.
- `bun run typecheck:development`: unit/browser tests, tools and Railway
  authoring.
- `bun run test:browser`: the existing Playwright browser suite; use
  `make test-browser` for its Django live-server wrapper.
- `make test`: backend, frontend, and browser targets from the Makefile.

`bun run` executes the existing Vite, Vitest/jsdom, Playwright, lint, and
typecheck scripts with Bun. Retain the existing Vitest configuration and
argument forwarding; `bun test` selects a different test runner. Package
executables used outside scripts run through `bunx --bun`. Use `bun outdated` to
inspect releases and `bun update --interactive` to select updates.
`bun run update` runs `bun update --latest` for all dependencies, followed by
the Browserslist data refresh. `make update` runs interactive Bun updates, the
standalone lock refresh, Python direct updates, and uv resolution; the Makefile
owns that sequence. See [Dependency Updates](dependency-updates.md).

The Prettier hook uses prek's `bun` language for installation and an explicit
`bun run --bun prettier` entry for execution. Selecting an installation language
alone does not override the upstream executable's shebang. Validate hook runtime
selection as well as package-script execution.

The local Django launcher starts automatic frontend rebuilds. Wait for each
successful build in the webserver logs, then refresh the browser manually. Use
`docker exec -w /app speleodb-monorepo-django bun run dev` only when Django was
launched independently and no watcher is already running. Type checks and
ownership audits run once before watching; subsequent saves compile only. Stop
the local webserver and its watcher before running `bun run build` for final
evidence and verifying the served manifest hash. Finite clean builds ensure
validation uses the current source set and removes accumulated watch output.

## Django and deployment

The Django manifest reader reloads by manifest mtime in DEBUG and caches in
production. Every template render shares one snapshot across asset tags and
includes, so a render uses one manifest version. Missing, malformed, unsafe,
duplicate, or wrong-type entries fail loudly. DEBUG/test may fall back to
registry-derived stable names before the first explicit build. URLs pass through
Django static storage, preserving local serving and S3/CloudFront behavior.

`compose/start` installs locked dependencies, completes `build:assets`, then
supervises Django and the `dev` watcher in separate process groups. Exiting
either process stops both, including their children. Use `build` for a finite
production build with the local webserver stopped. Neither the package scripts
`dev` nor `start` launches Django; `start` remains a finite asset-build alias.
See [development builds](vite-assets.md#development-builds).

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
guarded frozen install without rewriting the lock. Different physical hoisting
does not authorize changing a package version.

Verification covers the full Vitest suite, JavaScript lint, Railway
typechecking, a clean production build, and the browser cases relevant to the
change. Tooling contract tests check the shared version authorities,
frozen-install commands, script trust, lock metadata, and deployment automation.
They also assert Bun execution for scripts and spawned tools, so a compatible
API surface cannot conceal a different runtime. Run JavaScript and TypeScript
checks inside the existing application container and report the scope actually
exercised. The package manager adds no application runtime work; native tool
loading and output coherence prove the build remains usable without changing
frontend behavior.

Deployment verification also checks `collectstatic` and production module
MIME/CORS behavior. Full dependency refreshes retain the broader Python and hook
gates described in [Dependency Updates](dependency-updates.md).

## Monorepo command scope

Here, root JavaScript commands mean the web application's `apps/web` root. Run
web checks in the already-running application container at `/app`. The local
launcher selects the monorepo installer when `SPELEODB_LOCAL_PACKAGES=1`; that
installer consumes the root integration lock in an isolated Linux workspace.
Standalone mode uses the guarded frozen web lock install. The `/app` mount
prevents accidental ancestor-workspace discovery; changing directories to
`apps/web` on the host alone does not establish this isolation. The named
`/app/node_modules` volume also keeps Linux native packages separate from the
host's architecture. For a web-scoped change, run the web commands and prek
hooks; enclosing aggregate commands can enter unrelated applications. Do not
start a new stack for verification.

The native TypeScript checker checks the full source graph with
`allowJs: false`. A separate compiler API package supports typed ESLint;
`package.json` owns both package aliases and their versions. Source and template
audits enforce zero authored JavaScript and executable template expressions,
with exact vendor/generated exceptions. See
[TypeScript architecture](typescript-architecture.md) for environment
boundaries, compiler compatibility and build enforcement.

Contributor guidance:
[Tooling and package-manager changes](agent-practices.md#tooling-and-package-manager-changes).
