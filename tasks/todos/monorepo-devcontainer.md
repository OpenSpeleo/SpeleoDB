# Monorepo devcontainer integration

## Plan

- [x] Reuse `local.yml`, the Django image, `/entrypoint`, and `/start`
      unchanged.
- [x] Keep the web checkout mounted at `/app` while exposing the monorepo at
      `/workspace` to the development container.
- [x] Replace hard-coded GitLab identifiers with an idempotent first-run setup
      job that creates the local group and group access token.
- [x] Generate dynamic GitLab and RustFS settings in the ignored `.env` file
      that Django already loads, while keeping static credentials tracked.
- [x] Gate the workspace and webserver on healthy PostgreSQL, Redis, RustFS,
      fully ready GitLab, and successful local-service setup.
- [x] Run the existing `create_s3_local_buckets` management command from the
      setup job so both canonical RustFS buckets and policies exist.
- [x] Cover GitLab provisioning, env-file updates, Compose rendering, and
      idempotent reruns with focused tests.
- [x] Use the existing `python-gitlab` dependency for GitLab resources and
      access tokens instead of maintaining a manual HTTP client.
- [x] Disable access-token expiration enforcement in the local GitLab instance
      and replace any expiring development group token with a non-expiring one.
- [x] Copy `.env.dist` to the ignored `.env` on first setup, preserve an
      existing developer file, and populate every generated local value.
- [x] Create or repair the verified local Django superuser idempotently after
      migrations, using the documented development-only credentials.
- [x] Set the created or repaired local administrator's country to USA, using
      the canonical `US` field value required by `django-countries`.
- [x] Allow a temporary Compose project/container prefix to create an isolated
      fresh stack without renaming or deleting existing Docker volumes.
- [x] Isolate `/app/node_modules` in a project-scoped volume so container npm
      installs cannot replace host-native optional dependencies.
- [x] Exercise the complete isolated first-run path against new Docker volumes.
- [x] Verify migrations, the Vite watcher, and Django startup on port 8000.
- [x] Give the root devcontainer project-scoped container names so it can start
      alongside preserved standalone Compose containers.
- [x] Restrict root devcontainer creation to the web environment; never install
      or compile mobile, Rust, Tauri, or Java tooling during post-create.
- [x] Remove the experimental Rust/native dependency layer so both standalone
      and monorepo devcontainers use the same web-only image.
- [x] Exclude Compass and Ariane from root prek discovery while keeping their
      standalone configurations runnable from inside each subtree.
- [x] Remove obsolete toolchain references from scripts and documentation.
- [x] Verify the web image, merged Compose configuration, root hooks, and both
      subtree-local hook entry points.
- [x] Mount the web Linux `node_modules` volume at both `/app/node_modules` and
      `/workspace/apps/web/node_modules` in the monorepo workspace container.
- [x] Verify the native Rolldown binding and Vite pre-commit build from the
      `/workspace/apps/web` project path.
- [x] Reintroduce a minimal Rust toolchain only behind the monorepo Compose
      build argument required by the web runtime's local `openspeleo_core`.
- [x] Install `openspeleo_core` PEP 660 editable with Maturin's Cargo `dev`
      profile before web services start.
- [x] Persist uv, Cargo, and native target caches in a project-scoped volume and
      invalidate the uv build for every `src_rust` change.
- [x] Verify all four web library imports resolve from bind-mounted monorepo
      source while standalone web dependency resolution remains unchanged.
- [x] Normalize the shared native-build cache for `dev-user` so root setup and
      interactive prek/uv commands can safely reuse the same volume.
- [x] Move web dependencies from system Python into the image-owned
      `/opt/speleodb-venv`, outside the `/app` bind mount.
- [x] Keep uv caches directory-backed at `/app/.uv/cache` for standalone web use
      and `/monorepo-python-build-cache/uv` for monorepo native builds.
- [x] Limit privileged cache handling to a one-time ownership migration, then
      run uv, Cargo, prek, and interactive development as `dev-user`.
- [x] Give the monorepo web devcontainer its own Node dependency volume so a
      standalone root-run `/start` cannot contaminate its ownership.
- [x] Initialize that volume for `dev-user` before either application service
      starts, without recursively scanning it on every startup.
- [x] Run the monorepo workspace and webserver services as `dev-user` so npm,
      Vite, prek, and editor terminals share one ownership contract.
- [x] Reproduce and verify the exact Vite pre-commit build from
      `/workspace/apps/web`.

## Review

The root devcontainer composes on top of this subtree rather than duplicating
its services. The initial smoke test reached `/start`, but merely adding
hard-coded GitLab values to `.envs/.django` did not provision the corresponding
GitLab group/token or RustFS buckets and incorrectly assumed a stable group ID.
The follow-up work above replaces those placeholders with actual first-run
provisioning and Django's existing private `.env` loading path.

The final Compose graph makes `setup` depend on healthy PostgreSQL, Redis,
RustFS, and GitLab. GitLab's health check uses its complete readiness endpoint
and ensures a development-only root bootstrap token is available; the setup job
uses that credential to create or retrieve the group and create a scoped group
access token. Existing valid tokens are reused. Dynamic values are written with
mode `0600` to the ignored `.env`, then the existing Django S3 command creates
or verifies both canonical buckets and reapplies policy/CORS configuration. All
GitLab operations use `python-gitlab` resource managers; the setup code does not
construct GitLab API URLs or perform manual HTTP requests.

Verification:

- `docker compose -f local.yml config --quiet`
- root devcontainer merged Compose `config --quiet`
- shell and Ruby syntax checks for all bootstrap scripts
- focused provisioning and superuser tests: 9 passed
- Ruff and mypy: passed for provisioning, the management command, and tests

A complete `speleodb_fresh` Compose project was built against project-prefixed
volumes while the original `speleodb` containers remained stopped and all its
volumes remained present. The initial GitLab API attempt exposed that current
GitLab initially required `expires_at` for group access tokens because its
expiration-enforcement setting defaults to enabled. The development bootstrap
now disables that setting, creates both bootstrap and group tokens without an
expiration date, and rotates an older expiring group token once.

Live verification against the isolated GitLab instance reported
`require_personal_access_token_expiry=false` and `expires_at=null` for the
development group token. Django authenticated with that token after reading it
from the private `.env`; a subsequent setup run reported the group token and env
file already current, confirming that the non-expiring token is reused rather
than rotated. The temporary `speleodb_fresh` containers and volumes were removed
after verification at the developer's request; the original `speleodb` volumes
remained untouched.

The corrected setup recovered from that partial first run, populated the copied
`.env` with mode `0600`, validated the GitLab token/group, created both RustFS
buckets, applied every migration, and created the verified local superuser. The
existing `/start` installed the standalone JavaScript environment, started the
Vite watcher, passed Django system checks, and returned HTTP 200 from the
database-backed health endpoint inside the service. Direct checks also returned
Redis `PONG`, PostgreSQL readiness, valid GitLab group-token access, both bucket
names, and valid superuser credentials/email status. Restarting the one-shot
setup reported the env, token, group, buckets, and migrations already current
and repaired the existing superuser without duplication. No original volume was
removed or renamed during either testing or cleanup.

The repository-wide pre-commit run then exposed that `/start` had installed
Linux native npm dependencies into the macOS bind mount. Compose now overlays
`/app/node_modules` with a project-scoped volume, keeping container and host
native bindings independent.

After recreating only the isolated setup/webserver services, Docker reported the
new volume mounted at `/app/node_modules`; the Vite watcher and Django server
ran from it and the database-backed health endpoint still returned HTTP 200. A
root `npm ci` restored host-native dependencies, the production Vite build
passed, and every `apps/web` and root pre-commit hook passed.

The first real VS Code reopen then exposed a name-collision detail that a basic
Compose render did not catch: Dev Containers selected project name `web`, but a
project name does not rewrite explicit `container_name` values inherited from
the standalone file. The root override now assigns all seven active services a
`speleodb_devcontainer_*` default name while retaining `COMPOSE_INSTANCE_PREFIX`
overrides. Rendering the exact base, root override, VS Code build, and feature
Compose files from the failed command confirmed that every resulting service
name uses the devcontainer prefix; no preserved standalone name is reused.

The next real post-create run revealed that the root bootstrap was still much
broader than the selected web service: it installed Tauri system libraries,
compiled Trunk, wasm-pack, and Tauri CLI, then ran root `make setup` across the
monorepo. Trunk was killed by the container with `SIGKILL` during release
linking, but that compilation should never have occurred. The devcontainer
forwards only port 8000, installs only web editor extensions, uses the image's
`/opt/speleodb-venv`, and performs the standalone web shell initialization plus
the local runtime dependency sync during post-create. The monorepo image now
contains only the minimal Rust toolchain required by `openspeleo_core`; it does
not contain Tauri, Trunk, Java, mobile, or another application's toolchain.
Static checks confirmed that the post-create path contains no unrelated package
installation or application build command; an isolated HOME test confirmed
repeated execution adds the shell include exactly once. The merged Compose
service list contains only the seven services owned by `apps/web`.

The local-superuser bootstrap now treats USA as part of the fixed account
contract, persisting the `django-countries` value `US` on fresh creation and
repairing any different or empty value on later setup runs. The three focused
management-command tests pass, including the repair of an existing account whose
country was previously France; Ruff formatting/checks and mypy also pass for the
command and its tests.

The final boundary correction removed the experimental Rust/native dependency
layer and its Compose argument entirely. Both standalone and merged Compose
render only the web image's existing `DOCKER_BUILDKIT` argument. A clean image
build completed from the resulting Dockerfile; as `dev-user`, Python and Node
were available while Cargo, rustc, rustup, and shared rustup directories were
absent. Root `.prekignore` now prevents Ariane and Compass discovery without
weakening root file exclusions. Root discovery omitted both projects under prek
0.3.11 and 0.4.10, while Compass listed its local Cargo hooks from its
repository root and Ariane listed its local generic hooks from the plugin module
that owns its configuration. The launcher tests, root hooks, pinned Markdown
formatting, Compose validation, and root dry-run all passed.

The subsequent Vite failure exposed a second-path mount gap: `/app/node_modules`
used the project-scoped Linux volume, but `/workspace/apps/web/node_modules`
still came from the host bind mount. Root prek therefore reached macOS optional
packages when it executed the web hook from the monorepo path. The workspace
service now mounts the same named volume at both locations. Merged Compose
validation confirmed identical volume sources, an in-container inode check
confirmed both paths resolve to the same directory, and `npm run pre-commit`
completed the production Vite build from `/workspace/apps/web` on Linux/arm64.
The exact `prek run build-vite-assets --all-files` hook passed from the same
path in a disposable Compose container.

The later editable-library requirement deliberately narrows one conclusion
above: `openspeleo_core` is a direct web runtime dependency, so the monorepo web
image now opts into only the stable Rust/Cargo toolchain needed to compile its
PyO3 module. The standalone build keeps the argument disabled and continues to
use the published wheel. The opt-in layer precedes Python dependency
installation, while a project-scoped cache volume prevents repeated Cargo and uv
downloads.

The setup service runs the root synchronization helper before Django setup, so
the Linux extension exists before either web service can start. Post-create
reuses the same helper to give the interactive workspace container real PEP 660
editable metadata. Maturin uses Cargo's `dev` profile, and the package's uv
cache key includes all Rust source paths plus the Python and Cargo manifests.
Pure-Python edits are immediately visible; Rust edits require rerunning the
helper and restarting the webserver.

The first real root hook run found a permissions boundary in the new shared
cache: Compose setup initialized uv's files as root, then prek ran as
`dev-user`. Moving the web dependency graph into the image-owned
`/opt/speleodb-venv` removes the need for normal root package installation. The
helper now repairs an empty or legacy cache volume through a versioned one-time
migration, drops privileges, and performs uv and Cargo work as `dev-user`. The
uv cache remains the dedicated `/monorepo-python-build-cache/uv` directory, so
it stays persistent without being embedded in the virtual environment or
recursively repaired on every startup. Standalone containers continue using
`/app/.uv/cache`.

A clean standalone image build created `/opt/speleodb-venv`, resolved Django
from that environment as `dev-user`, retained `UV_CACHE_DIR=/app/.uv/cache`, and
contained no Cargo binary. The monorepo image reused the Rust toolchain layer;
its disposable sync replaced the published core wheel with the editable local
project, loaded both Python and the compiled CPython 3.14 Linux extension from
`packages/python/openspeleo_core/src_python`, and wrote to the preserved
`/monorepo-python-build-cache/uv` directory as `dev-user`.

The next root hook run exposed an independent Node ownership failure: the shared
volume and `.vite-temp` had been populated by the root-running webserver, while
prek ran as `dev-user`. The monorepo override now assigns the Node volume an
explicit `COMPOSE_INSTANCE_PREFIX` name, mounts it at both paths in all
application services, and initializes its root ownership during setup. The
workspace and webserver run as `dev-user`, preventing later root-created files
without paying for a recursive ownership scan on every startup.

Validation created the default devcontainer-specific volume without touching the
preserved standalone volume. Standalone-style `npm ci` ran as `dev-user`, the
exact `npm run pre-commit` command succeeded from `/workspace/apps/web`, Vite
transformed 153 modules, and a bounded ownership scan found no dependency entry
owned by another user. The project-qualified
`prek run apps/web:build-vite-assets --all-files` hook then reported `Passed`
from the same volume.
