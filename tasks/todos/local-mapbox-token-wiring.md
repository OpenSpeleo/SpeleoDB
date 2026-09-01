# Local Mapbox Token Wiring

## Plan

- [x] Confirm the browser error originates from the local placeholder token, not
      Django CORS configuration.
- [x] Make the root `.env` Mapbox token authoritative for local Django services.
- [x] Add a regression test that prevents `.envs/.django` from shadowing the
      root token again.
- [x] Document local token ownership and the tokenless ESRI fallback.
- [x] Recreate the local Django services and verify the active environment,
      rendered map context, focused tests, full JavaScript suite, lint, and
      production build.

## Review / Results

The tracked `unused-local-token` value was removed from `.envs/.django`.
`local.yml` now explicitly interpolates the developer-owned root
`MAPBOX_API_TOKEN` into the shared Django service definition, which also covers
`django-webserver`. An empty or missing root value remains safe because the
existing map-source implementation selects tokenless ESRI Satellite.

The webserver was recreated without interrupting the active devcontainer test
process. Its environment matches the root `.env`, Django settings see a public
`pk.*` token, and an authenticated render of `/private/map_viewer/` contains the
configured token and not the placeholder. The running server returned HTTP 200.

Verification:

- `docker compose -f local.yml config --quiet`: passed.
- Compose regression test: `1 passed`.
- Full JavaScript suite: `50 passed` files, `933 passed` tests.
- JavaScript lint: passed.
- Ruff check/format and mypy for the new Python test: passed.
- Clean Vite production build with the development watcher stopped: passed.
- `git diff --check`: passed.

## Devcontainer reconciliation follow-up

- [x] Confirm the rendered Compose model has the configured token while the
      running Django containers still have the stale placeholder.
- [x] Reconcile the workspace and webserver services through Compose when an
      existing devcontainer stack is reopened.
- [x] Add regression coverage and synchronize the root devcontainer docs.
- [x] Recreate the affected services and verify the active token classification,
      Django response, focused tests, and root monorepo tool suite.

The recurrence came from the monorepo adding a host restart workflow beside the
normal Compose lifecycle. Bind-mounted code changed immediately, but raw
container restarts retained the old immutable environment. The separate path was
removed: standalone and devcontainer startup now both use the complete Compose
build/up graph, including dependency ordering, health checks, setup, and
application services.

Follow-up verification:

- Active container environment and Django settings: configured, not printed.
- Authenticated `/private/map_viewer/`: HTTP 200, configured token present,
  placeholder absent.
- Live loopback response from the shared container network: HTTP 200.
- Compose configuration tests: 4 passed, 1 skipped.
- Focused map source/initialization tests: 21 passed.
- Root tool suite through direct Node, npm, and Make entrypoints: 16 passed in
  each run.
- Full merged `docker compose up --detach --build` smoke test: rebuilt the local
  PostgreSQL and Django-family images, evaluated every service, waited for all
  dependency health checks, completed setup with exit code zero, and started
  both application services.
- Devcontainer JSON, merged Compose configuration, and `git diff --check`:
  passed.
