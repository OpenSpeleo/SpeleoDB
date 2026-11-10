# Frontend dates

Product pages use the browser's locale and timezone for timestamps. The shared
formatter in `frontend_common/presentation/dates.ts` displays the year, short
month, day, hour, and minute without a timezone suffix. API timestamps retain
their offset or `Z`; presentation never removes the offset before parsing.

Calendar dates, such as experiment dates, installation dates, and inspection or
expiry dates, have no timezone. `formatDate` parses and formats `YYYY-MM-DD`
using UTC calendar components while retaining the browser's locale. The selected
day neither moves backwards west of UTC nor disappears when a timezone has
skipped a calendar day. Timestamp and `Date` inputs still use the browser
timezone. Month-only chart labels preserve month precision. Native date inputs
retain `YYYY-MM-DD` values, with today's default taken from the browser's local
calendar.

## Template and controller ownership

Django templates load `filter_utils` and use `{% local_date value %}`. The tag
emits a semantic `<time>` with an ISO `datetime` attribute and a
`data-local-date` mode distinguishing timestamps from calendar dates. An
optional second argument preserves an existing missing-value placeholder. The
common application bootstrap formats these elements before initializing route
controllers. It does not need page-specific scripts or a mutation observer.
Static editorial months use the same `<time>` contract with
`data-local-date="month"` and a `YYYY-MM` value.

Dynamic controllers and shared private/public map modules call `formatDateTime`
or `formatDate` directly. This includes revision history, dashboard activity and
heatmap tooltips, GIS and tag lists, exports, commit selectors, map popups and
logs, fleet history, and experiment data. Experiment grid formatters preserve
raw ISO values for chronological sorting. Cylinder map labels carry a separate
formatted property so the stored installation date remains unchanged.

Relative Git ages represent elapsed time between timezone-aware instants. The
dashboard's Today/Yesterday grouping follows browser-local days. Sensor expiry
countdowns compare calendar-day ordinals, avoiding daylight-saving days with
different elapsed lengths. Monthly contribution counts remain the backend's
existing calendar aggregates; only their labels are formatted in the browser.

Framework-provided Django admin fields, email content, and downloaded file
formats retain their own contracts. Static editorial month labels retain their
original precision.

## Verification

Template regression tests preserve timestamp offsets, seconds, date-only values,
and missing-value placeholders. Frontend regressions exercise actual renderers
and bootstrap hydration across UTC offsets, midnight boundaries, and daylight
saving transitions. Date formatting and template transport belong to these
Vitest and pytest checks; the browser suite covers complex UI interactions.

Run tests and production builds inside the existing application container as
specified in `AGENTS.md`. After changing browser timezone emulation, reload the
page so cached `Intl.DateTimeFormat` instances use the new browser settings.
