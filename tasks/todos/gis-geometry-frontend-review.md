# GIS Geometry frontend adversarial review

- [x] Review private/public map integration, shared rendering, management forms,
      templates, panel interactions, and asynchronous metadata loads.
- [x] Refine corrective scope: preserve locally saved records across metadata
      retries without retaining unrelated rows omitted by the server; restore
      keyboard focus when panel controls are hidden or rebuilt.
- [x] Implement metadata race and keyboard focus corrections.
- [x] Add deferred-response and keyboard regression tests; run focused tests in
      the existing application container.
- [x] Record actionable findings and verification results for the main review.

## Findings

- P2: Metadata retry failure clears locally saved geometry; a delayed successful
  retry can overwrite a newer revision or erase a concurrent creation.
- P2: Panel expansion/collapse hides the focused control and list refreshes
  remove the focused toggle, interrupting keyboard navigation.

## Corrective plan review

Preserve only local records changed since request start when the server omits
them. Use the existing revision-aware upsert for returned rows, rather than
creating a second revision policy. Keep retry errors visible. Restore focus only
when a control in this panel owned focus; never pull it from the editor.

## Verification

The existing application container passed 42 focused tests across geometry
metadata/rendering, the geometry panel, and both management controllers. Tests
cover deferred metadata after create/save, failed retries retaining local data,
unchanged revoked/deleted rows disappearing, newer server permissions, panel
focus transitions, toggle focus after browser blur, and focus moved elsewhere
during a pending request. The editor reviewer covers the visible close-focus
fallback. The main review runs the complete suites and pre-commit hooks.

## Browser review correction

Opening the editor directly from a URL captures `document.body` as its prior
focus target. A connected element is not necessarily focusable: close now checks
that focus actually moved, skips disabled and hidden/inert controls, and tries
the visible toolbar/panel fallbacks. Regression tests cover direct opening,
hidden, disabled, and detached triggers, and preserving a usable original
trigger. The focused editor suite passed after this correction.
