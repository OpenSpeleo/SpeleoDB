# Monorepo Native and Tooling Dependency Development

## Boundary

The standalone SpeleoDB image installs its locked Python dependencies from
published distributions and remains Rust-free by default. The enclosing
monorepo can opt into `DOCKER_INCLUDE_MONOREPO_RUST_TOOLCHAIN=1` to develop the
PyO3-backed `openspeleo_core` web runtime dependency from local source.

This option installs stable Rust and Cargo before the Dockerfile's Python
dependency layer. It does not install or build Compass, Tauri, Trunk, wasm-pack,
Java, mobile tooling, or another application repository.

## Editable Build

The root Compose setup runs
`.devcontainer/sync-openspeleo-core.sh` before the normal Django setup. The
helper uses the package's standalone lock and performs an inexact uv sync into
the image-owned `/opt/speleodb-venv` virtual environment. The environment lives
outside `/app`, so the application bind mount cannot hide it or mix a Linux
environment with a host checkout. Inexact synchronization is required because
the environment also contains the complete web dependency graph.

`openspeleo_core` is a mixed Python/Rust Maturin project. Its editable build
uses Cargo's `dev` profile explicitly. The Python sources and generated Linux
extension resolve from the bind-mounted
`packages/python/openspeleo_core/src_python` tree, while the standalone web
lock remains independent and continues to resolve PyPI outside the monorepo.

The interactive workspace's post-create step runs the same helper so its Python
environment records the PEP 660 editable installation as well. Pure-Python
changes are immediately visible. After changing Rust code, run:

```bash
/workspace/.devcontainer/sync-openspeleo-core.sh
```

Restart the Django webserver after rebuilding because CPython cannot safely
replace a loaded extension module in place.

## Cache Contract

The root Compose project mounts a named cache at
`/monorepo-python-build-cache`. It owns uv downloads/builds, Cargo registry
data, and the Cargo target directory so Linux artifacts do not collide with
host-native outputs. uv continues to use a normal cache directory at
`/monorepo-python-build-cache/uv`; Cargo uses sibling directories in the same
volume. Standalone web containers retain their separate uv runtime cache at
`/app/.uv/cache`.

The one-shot Compose setup service starts as root, but root only creates the
cache directories and performs a versioned ownership migration when an empty or
legacy volume lacks its marker. The helper then drops to `dev-user` before
running uv or Cargo. Interactive terminals, prek, the virtual environment, and
all future cache entries therefore share one owner without recursively scanning
the cache on every sync. Do not move the virtual environment below `/app` or
merge either cache directory into it.

Custom uv cache keys replace uv's defaults. The core package therefore lists
all of these explicitly:

- `pyproject.toml`;
- `Cargo.toml`;
- `Cargo.lock`;
- every path matched by `src_rust/**/*`.

Any Rust source change invalidates the cached editable build. Python source is
not part of the native cache key because editable imports read those files
directly.

## Node Dependency Ownership

The monorepo override gives `/app/node_modules` an explicit volume name derived
from `COMPOSE_INSTANCE_PREFIX`. The default is
`speleodb_devcontainer_local_web_node_modules`, which is distinct from the
standalone Compose project's Node volume. This prevents a standalone root-run
`/start` from leaving files that the monorepo's `dev-user` cannot replace.

All monorepo application services mount that same volume at both
`/app/node_modules` and `/workspace/apps/web/node_modules`. The second mount is
required because root prek discovery executes the web hooks through the
monorepo path. Allowing that path to fall through to the host bind mount can
load the wrong platform's optional native packages.

The one-shot setup service calls
`.devcontainer/prepare-web-node-modules.sh` as root before application startup.
It recursively migrates ownership only when the volume root is not already
owned by `dev-user`. The workspace and webserver services themselves run as
`dev-user`, so subsequent `npm ci`, Vite temporary files, prek builds, and
editor commands preserve ownership without another scan.
