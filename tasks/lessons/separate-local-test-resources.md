# Keep local test resources isolated from development resources

When asked to set up a test environment "the same as" development, interpret
that as equivalent provisioning behavior, not shared credentials or namespaces.
Confirm resource isolation explicitly before implementation.

For the local SpeleoDB stack, development and tests may use the same GitLab and
RustFS service instances, but they must have separate GitLab groups, group
tokens, and storage buckets. The setup job must provision and validate each
resource set independently and write only the matching values to each private
environment file.
