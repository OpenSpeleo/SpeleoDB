# Keep pytest discovery scoped to source

A custom `norecursedirs = ".uv/*"` replaced pytest's default exclusions and made
test collection scan tens of thousands of scratch repository directories.

- Prefer explicit source roots in `testpaths` and inherit pytest's maintained
  directory exclusions. Do not assume an exclusion setting extends defaults.
- Include every established test root and standalone `tests.py` modules.
- Profile collection separately from database setup and test execution, inside
  the requested container with competing runs stopped.
- Compare ordered node IDs and counts before and after narrowing discovery.
  Normalize only known nondeterministic parameter labels, preserving their
  multiplicity; do not shrink test coverage to improve collection timing.
