# Align application timestamps with Django's clock

- [x] Reproduce the two reported failures and inspect dispatch timestamps.
- [x] Audit the repository for captured clock callbacks and non-Django wall
      clocks.
- [x] Use explicit Django timestamps when creating jobs and attempts, preserving
      dispatch leases and finite retries.
- [x] Fix captured factory clocks and align OGC, debug tags, and storage test
      timestamps.
- [x] Run retry budget, lifecycle, and clock regressions, Ruff, and mypy.
- [x] Record the cause, verification, and any applicable testing lesson.

## Plan check-in

The user requested a fix for failed publication and stale publication tests.
Both failures reproduced: model defaults retain the original function while the
tests replace `timezone.now`, placing `dispatch_after` ahead of the test clock.
The expanded user request covers every application wall-clock occurrence. Use
one Django timestamp for attempt creation and initial dispatch; keep idiomatic
model fallback defaults and elapsed-duration monotonic clocks. Five factory
callbacks also retain the original clock; OGC and the debug tag use other
clocks. Preserve unrelated pytest collection work in the shared workspace.

## Review

Fixed both reported failures at the centralized production creation sites. All
initial, automatic, and manual attempts get explicit Django creation and due
timestamps. Five factory fields now look up the clock inside lazy callbacks;
OGC, the debug template tag, and four CloudFront expiry assertions also use
Django. UTC wire timestamps, elapsed timers, and idiomatic model fallback
defaults remain valid. No migration or new query is needed.

Initial verification: 92 passed, 1 skipped across retry budgets, lifecycle,
retention, export API, factory timestamps, and private URL tests. OGC helper and
debug tag suites added 75 passes. Full mypy passed 708 source files. Ruff and
format checks passed. Independent review found no actionable issue. The final
factory regression rerun passed all three tests after the lint-driven
LazyAttribute adjustment. Total distinct cases: 167 passed and 1 skipped.

The user's subsequent mypy report identified two PluginReleaseFactory fields
missing annotations after the LazyAttribute adjustment. Both now match the other
timestamp declarations' explicit `Any` annotations. Full mypy was rerun after
this final edit and passed all 708 source files; factory Ruff also passed.
