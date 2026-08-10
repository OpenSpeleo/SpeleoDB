# Migration Constraint State Names

When replacing a Django constraint, obtain the name from the immediately
preceding migration state, not from an older migration or memory. Constraint
renames in intermediate migrations mean the database and migration state can
legitimately use a newer name even when the original constraint semantics are
unchanged.

Before handing off a migration:

- inspect every migration that mentions the constraint;
- use the name present at the dependency migration;
- exercise the forward migration from that exact dependency and restore the
  latest migration graph in a migration test.

This prevents `RemoveConstraint` from failing during `migrate` with
`ValueError: No constraint named ...`.
