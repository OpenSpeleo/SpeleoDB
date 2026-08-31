# Zed devcontainer port publication

- [x] Publish Django port 8000 from the workspace container.
- [x] Share the workspace network namespace with the webserver.
- [x] Route container-only dependencies through Compose service DNS.
- [x] Remove the setup service's inherited host-network dependency.
- [x] Keep browser-facing local object-storage URLs on `localhost:9000`.
- [x] Preserve standalone and root-devcontainer test service reachability.
- [x] Bind Django's published debug port to host loopback only.
- [x] Make the devcontainer service set explicit across editors.
- [x] Render and validate the merged Compose configuration.
- [x] Verify Django is reachable from the host on port 8000.

## Review

The root devcontainer now follows the same Docker-level port-publication pattern
as the known-working Train Captain project. `django` publishes port 8000 and
`django-webserver` shares its network namespace. PostgreSQL, Redis, GitLab, and
RustFS use Compose DNS internally, including during setup; local GitLab and
object-storage URLs generated for the browser remain on `localhost`. The Django
debug port is restricted to the host loopback interface.

Static Compose rendering, the root monorepo test suite, Ruff, and focused Django
settings tests pass. After recreating the stale Zed application containers,
Django is reachable from the host on port 8000. Host-side checks also confirmed
GitLab, RustFS, PostgreSQL, and Redis remain reachable on their published ports.
