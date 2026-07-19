# Local Infrastructure Static Contracts

## Lesson

Canonical local infrastructure names must remain explicit when the repository
owns them. Do not derive fixed development or test bucket names from runtime
settings: a typo or unexpected environment override can silently provision the
wrong resource while appearing successful.

Likewise, a Docker Compose service with `restart: "no"` is not a once-ever
initializer when another service lists it under `depends_on`. Compose schedules
the completed container again on a later `up` operation.

A Compose project name scopes generated resource names, but it does not rewrite
an explicit `container_name`. A devcontainer that layers over a standalone
Compose file must therefore override every active fixed container name when the
standalone containers are intended to remain preserved.

Repository-wide toolchain support is not permission to provision every toolchain
when a scoped devcontainer opens. Post-create commands are on the critical
startup path: they must install only what the selected application needs and
must never invoke a root bootstrap that expands into unrelated workspaces.

A native package that is part of the selected application's runtime is a
different boundary from an unrelated repository hook. Its compiler can be
included through an explicit monorepo-only image option, while the standalone
image remains unchanged. Install that toolchain before dependency layers, keep
its cache project-scoped, and make native source part of the package manager's
cache key.

A native development overlay should not mutate system Python. Put the web
dependency graph in an image-owned virtual environment outside the application
bind mount, keep uv and Cargo caches in their dedicated project-scoped volume,
and run package-manager work as the remote user. If a root-started setup service
must prepare the volume, limit it to a versioned one-time ownership migration
and drop privileges before invoking uv or Cargo. Merely mounting the same volume
does not make legacy root-created metadata writable, while recursively repairing
it on every startup wastes the cache's performance benefit.

Do not expand an application image solely so root orchestration can run another
standalone repository's hooks. Exclude that repository from root hook discovery
and run its hooks from its own directory and toolchain instead.

When the same source tree is bind-mounted at both an application path and a
monorepo path, a dependency-volume overlay applies only to its exact container
target. Any tool that enters through the second path can fall through to the
host's platform-specific dependency directory. Mount the same named volume at
both dependency paths rather than reinstalling packages or adding native
bindings manually.

Sharing both paths is not enough when different Compose modes write as different
users. Give the monorepo its own explicitly prefixed Node volume, initialize its
root for the remote user before application services start, and run npm/Vite as
that user. Checking ownership at the volume root avoids an unconditional
recursive `chown`; isolating the volume prevents a standalone root-run npm
install from invalidating that shortcut.

A fixed bootstrap account is also a complete local-data contract. Required
profile fields must be populated explicitly, and idempotent setup must repair
those fields on accounts created by an older version of the bootstrap.

## Rules

- Keep the canonical development and test bucket names visible in the
  provisioning loop and document them as part of the local infrastructure
  contract.
- Add a regression test proving an `AWS_STORAGE_BUCKET_NAME` override cannot
  change the buckets provisioned by the local command.
- Keep create-once setup jobs out of normal application dependencies.
- Profile-gate explicit initialization jobs and invoke them only during initial
  bucket setup or an intentional reconfiguration/migration.
- Use `docker compose --dry-run` when reviewing whether a supposedly one-shot
  service will be scheduled by normal startup.
- When a devcontainer inherits a Compose file with explicit container names,
  inspect the fully merged configuration and ensure every active service has a
  devcontainer-specific name; changing only the Compose project name is not
  isolation.
- Keep the web devcontainer's post-create scope equivalent to the standalone web
  application. The local PyO3 dependency may use the image's minimal
  monorepo-only Rust toolchain; Tauri CLI, mobile, Java, monorepo-wide setup,
  and non-web compilation remain in their owning repositories or CI jobs.
- When root tooling runs web commands from `/workspace/apps/web`, keep its
  `node_modules` target backed by the same named volume as `/app/node_modules`.
  Never expose host-native optional packages through one alias of the checkout.
- Keep the monorepo Node volume separate from the standalone Compose volume,
  prepare it before application startup, and keep the workspace/webserver
  process user aligned with prek. Never make every startup recursively traverse
  `node_modules` to repair ownership.
- With host networking, do not add Docker `EXPOSE` or Compose `ports` entries
  solely for VS Code. Use `forwardPorts` in `devcontainer.json` when reopening
  in a Dev Container, and workspace-level remote auto-forwarding when running
  plain Docker Compose through Remote SSH or Tunnels.
