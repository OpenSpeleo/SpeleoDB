# Personal Landmark Uniqueness

## Lesson

When a model has creator/provenance (`created_by`) and a permissioned
aggregate (`collection`), do not keep a parallel creator FK as a shadow owner.
Personal ownership should be represented by a real personal aggregate with the
same permission machinery as shared aggregates.

## Rule

- Keep creator/provenance fields separate from access control.
- Give each user exactly one personal collection, created lazily at first need.
- Make child rows belong to a collection, including personal rows.
- Scope duplicate constraints to the collection, not to creator identity.
- Remove stale child-level owner FKs once migration backfill can derive
  `created_by` and personal collection membership from them.
- When removing a non-null owner FK, make the rollback path explicit: re-add
  the old column as nullable, repopulate it from the new aggregate ownership,
  then restore the old non-null constraint.
- Do not use `SET_NULL` for the aggregate FK if hard deletion would reclassify
  aggregate rows as personal rows. Prefer preserving the aggregate via soft
  delete or deleting member rows via cascade on physical deletion.
- Include the aggregate scope in import or `get_or_create` lookups so importing
  into a collection cannot be suppressed by an unrelated personal row at the
  same coordinates.
