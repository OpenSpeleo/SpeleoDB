# Nix tools with uv and npm

## Build boundary

`compose/Dockerfile` starts from the pinned official `nixos/nix` image.
`flake.nix` defines tools and system libraries, `flake.lock` pins Nixpkgs 26.05,
and `.node-version` selects the Node major. The Dockerfile installs those
packages with `nix build`, then runs ordinary application commands:

```bash
uv sync --frozen --extra local       # development
uv sync --frozen --extra production  # production build
npm ci
npm run build                       # production assets
```

Nixpkgs 26.05 provides uv 0.11.21, which predates this project's dependency
overrides. The flake therefore fetches Astral's static uv 0.12.17 binaries with
`fetchzip`, a fixed-output derivation with a SHA-256 hash per Linux
architecture. `flake.lock` pins only Nixpkgs.

`uv.lock` and `package-lock.json` remain authoritative for application
dependencies. The flake contains package lists and a development shell;
application installation stays in Docker. Compose retains service readiness,
networking, volumes, and startup order.

## Environments and targets

The `runtime` package set supplies Python and application libraries/utilities at
`/opt/runtime`. The `development` set supplies Node/npm, uv, compilers, and
editor tools at `/opt/development`. The `monorepo` set adds stable Rust and
Cargo for editable `openspeleo_core`. `nix develop` exposes runtime and
development tools on supported Linux hosts without installing application
dependencies.

`local.yml` selects the Dockerfile's `development` target. The monorepo override
sets `DOCKER_INCLUDE_MONOREPO_RUST_TOOLCHAIN=1`. Python dependencies live in the
writable `/opt/speleodb-venv`, outside `/app`; uv uses Nix's Python without
downloading another interpreter. The development image uses `nix-ld` for editor
binaries that expect a conventional Linux loader. It also links Nix's libc and
libstdc++ into `/usr/lib`, where VS Code's prerequisite checker looks for them.
The checker verifies the real library versions; glibc stays off the global
`LD_LIBRARY_PATH`.

`/start` runs migrations, `npm ci`, the Vite watcher, and Django. Existing
`dev-user` ownership, Node volumes, source overlays, cache mounts, Git trust,
and editable Rust synchronization remain in place. Startup does not evaluate Nix
or download toolchains.

The image build also runs `compose/prepare_node_modules` to initialize the Node
directory and catch missing tools such as `getent` before container startup.

The final/default `production` target copies the venv and compiled application
from its build stage onto the runtime stage. It retains the official Nix base
and runtime packages; Node/npm, uv, compilers, Rust, and `node_modules` stay in
the build stage. Dependency layers precede application source for Docker
caching.

```bash
docker build --target development -f compose/Dockerfile .
docker build --target development \
  --build-arg DOCKER_INCLUDE_MONOREPO_RUST_TOOLCHAIN=1 \
  -f compose/Dockerfile .
docker build --target production -f compose/Dockerfile .
```

## Compose image ownership

`django` is the only service that builds the shared Django image. `setup`,
`celery-worker`, and `celery-beat` use that image without their own `build`
blocks. `django-webserver` retains its separately tagged image and shares
Django's build configuration. PostgreSQL uses the upstream `postgres:16` image
directly. There is no custom PostgreSQL build, backup-script installation, or
`/backups` mount. Existing database data remains in the same named volume.

Compose adds a service label to each image it builds. Giving several buildable
services the same image tag produces distinct final images that overwrite one
another's tag, leaving untagged images behind. Keep one build owner per tag;
Nix's intermediate stages stay in BuildKit's cache.

Normal full-project Compose and editor builds build the shared image before
creating containers, including setup. On a clean checkout, build `django` before
invoking an image-only service by itself. `docker compose build --print` should
list only `django` and `django-webserver`, each with a unique tag. Rebuilding a
changed image can still leave an older image untagged; this layout prevents
duplicate exports during the same build.

## Deployment and verification

### Docker-managed writable Nix store

The Dockerfile mounts a writable Docker cache directly at `/nix`. It contains
normal unpacked package files in `/nix/store` and the Nix database under
`/nix/var/nix`. The cache is seeded from the pinned official Nix base image;
subsequent Nix builds run directly in that store and can reuse completed work.
This is the working Nix store, not an export of compressed binary-cache files.

Required package closures are copied into the images. Running applications
remain independent of the builder cache, and uv/npm installation remains
unchanged. Local, CI, and Railway builds use the same Dockerfile without host
cache directories, APFS setup, preparation scripts, editor initialization hooks,
or named build contexts.

Docker owns the cache and may garbage-collect it. The existing CI layer-cache
export does not transfer mutable cache mounts; a new builder may need to fetch
Nix dependencies again. Ordinary Docker layer reuse still applies. A warm Nix
store does not make the complete application build offline: uv/npm and image
bootstrap may require network access.

### Deployment

`.railway/railway.ts` selects this Dockerfile for web, worker, and scheduler
from standalone `OpenSpeleo/SpeleoDB`; sibling monorepo packages are never
production inputs. Start commands and predeploy migrations, schedule
installation, and static collection remain unchanged. Build configuration edits
do not deploy it.

Web CI builds Linux amd64 production without publishing; monorepo CI builds
development through Compose. Flake outputs support Linux amd64 and arm64. Run
repository tests in the existing application container; tests in an older image
do not validate the new runtime. After an authorized rebuild, verify native
imports, PostgreSQL/libpq, geospatial transforms, FFmpeg, TLS, Git, editor
startup, permissions, setup, HTTP, Celery, and editable Rust builds.

Update `flake.lock` deliberately when changing system packages, then rebuild
both targets. Application lockfiles change when application dependencies change.
