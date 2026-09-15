# Use Django's clock for application timestamps

The user requires `timezone.now()` so application timestamps stay aligned. Two
retry-budget failures arose because replacing `timezone.now` in tests did not
replace the original callable captured by a model field default. The new attempt
was therefore slightly later than the clock dispatch used to find due work. This
was a captured-clock mismatch, not a naive/aware datetime mismatch.

- Read current application wall time through `django.utils.timezone.now()`.
- At a service transition, use one timestamp for related creation/due fields.
  Check all callers, including automatic and manual retry paths.
- Keep idiomatic model defaults as fallbacks. Pass explicit transition
  timestamps when creation must follow the service's current clock.
- Resolve the Django clock inside lazy test-factory callbacks; directly passing
  `timezone.now` captures the earlier callable.
  `LazyAttribute(lambda _: timezone.now())` evaluates it when each instance is
  built.
- Preserve UTC output for timestamps labeled `Z` and test an active non-UTC
  timezone. Use Django epoch timestamps for signing assertions and debug tags.
- Keep monotonic clocks for elapsed-time deadlines. Do not replace them with
  wall time or modify historical migrations merely to change clock lookup.
- Changing a factory declaration from `LazyFunction` to `LazyAttribute` can
  require an explicit field annotation. Match the existing factory's typed
  declarations and rerun mypy after the final callback edit, even if an earlier
  mypy run passed.
