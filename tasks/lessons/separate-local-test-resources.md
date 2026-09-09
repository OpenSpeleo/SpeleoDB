# Keep local test resources isolated from development resources

When asked to set up a test environment "the same as" development, interpret
that as equivalent provisioning behavior, not shared credentials or namespaces.
Confirm resource isolation explicitly before implementation.

For the local SpeleoDB stack, development and tests may use the same GitLab and
RustFS service instances, but they must have separate GitLab groups, group
tokens, and storage buckets. The setup job must provision and validate each
resource set independently and write only the matching values to each private
environment file.

Run Linux ownership and container-bootstrap tests with temporary state on a
native Docker volume. A macOS bind mount does not reproduce Linux `chown`
semantics; mount source read-only and keep generated state off that mount.

Before a full live-service run, check Docker memory pressure and authenticated
service health. Concurrent builds can cause the Docker VM to kill GitLab workers
without restarting the container. Diagnose that infrastructure failure instead
of increasing application retry budgets to hide it.
