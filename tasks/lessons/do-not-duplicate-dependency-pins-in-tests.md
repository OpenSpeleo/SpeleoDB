# Do Not Duplicate Dependency Pins in Tests

## Correction

An installed software version was copied from `package.json` into a unit test.
That made routine dependency updates fail until the same version was manually
changed in two places.

## Rule

Treat dependency manifests and lockfiles as the sole sources of truth for
installed software versions. Unit tests must not hard-code package releases,
lockfile-format versions, resolved tarball versions, or versioned install-script
keys.

When a dependency contract matters, test stable properties instead: required
package names are present, the root lockfile graph matches the manifest,
resolved nodes contain integrity metadata, and packages with install scripts
have matching explicit approvals. Keep version assertions only for product data
formats, protocol behavior, or intentionally frozen compatibility fixtures.
