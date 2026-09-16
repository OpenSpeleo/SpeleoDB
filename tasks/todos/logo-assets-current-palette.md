# Current logo asset references

- [x] Inspect the renamed dark and light SVGs and locate stale logo references.
- [x] Update asset documentation and palette guidance to match the current
      files.
- [x] Verify documented colors, geometry, and embedded-icon behavior in the
      container.

Scope: document `logo-sdb-dark.svg` and `logo-sdb-light.svg`, their shared blue
(`#3852fc`), and their white/almost-black foregrounds. Preserve existing
artwork.

Review: container checks confirmed both documented filenames, foreground colors,
shared blue on both accent paths, matching dimensions and all 33 path
geometries, and the unchanged embedded icon with the light variant's
alpha-preserving filter. Only documentation changed; the application test suite
was not rerun.
