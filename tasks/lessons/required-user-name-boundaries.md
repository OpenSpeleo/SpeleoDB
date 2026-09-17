# Required names need write-boundary enforcement

- `blank=False` and `REQUIRED_FIELDS` do not validate ordinary model/manager
  saves. Pair clear application validation with a database check when every
  persisted row must satisfy an invariant.
- Inspect the complete signup lifecycle before adding a constraint. allauth
  saves before the custom signup hook, so required custom fields belong in the
  adapter before that first save, including headless signup.
- Validate after transformations that can empty input. Serializer field
  validation happens before the shared sanitization mixin returns its result.
- Keep display-name validation separate from Git identity formatting. Git's CLI
  is stricter than direct commit serialization; test the actual installed Git
  with real local repositories and retain a defensive author fallback.
- Preserve unrelated partial saves and avoid fetching deferred fields merely to
  validate a column that is not being written.
- Database constraints need migration repair and SQLite/PostgreSQL tests; repair
  data before adding the check and retain repaired data on rollback.
