# Second adversarial editor review

- [x] Re-review the complete editor, geometry validator, camera, and event
      dispatcher, including the first review's fixes.
- [x] Reproduce actionable failures without changing production behavior.
- [x] Add deferred clipboard regression coverage for close/reopen and fallback.
- [x] Bind clipboard completion to its initiating editor session and nodes.
- [x] Prevent opening another draft while a conflict reload owns the editor.
- [x] Run focused container tests and review other asynchronous editor
      operations.

## Corrective plan

P2: `copyDraft()` allows closing or replacing a draft while clipboard permission
or writing is pending. Completion then dereferences removed nodes or writes old
draft UI state into the new editor. A read-only container reproduction throws
`TypeError: Cannot read properties of null (reading 'copyFallback')`.

Capture the initiating session and nodes, then discard success/failure UI work
if the session changed. Keep the clipboard write itself and same-session
fallback unchanged. This needs no cancellation framework or new configuration.
The root reviewer reviewed and approved this corrective plan.

P1: after a 409 conflict, restoring the original name/coordinates makes a draft
unchanged without removing its reload controls. While a confirmed reload is
pending, the top-bar Create Geometry or another Edit action can replace the
session because `close()` refuses to close a saving session but the entry point
continues. Reload completion then discards the replacement draft. Guard both
entry points whenever the current session is saving, regardless of dirty state.
The root reviewer confirmed this reachable data-loss scenario and approved the
additional guard and regressions.

## Verification

Four clipboard tests and both conflict-reload entry tests failed before their
corrections. All 103 focused tests covering editor lifecycle, geometry
validation, camera padding, and event dispatch now pass in the application
container; focused ESLint also passes. Existing synchronous clipboard fallback
and asynchronous rejection fallback remain covered.

The remaining asynchronous operations retain their existing ownership gates:
opening serializes detail loading with `_opening`, save/reload prevent closing
or switching sessions with `saving`, and the production viewer initializes the
editor only once. No further actionable findings in camera framing, geometry
validation, or the already-corrected mouse/touch/keyboard paths.
