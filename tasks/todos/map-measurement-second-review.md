# Second adversarial review of the private map ruler

## Scope and plan

The user requested a fresh full review through the review-agent skill after
commit `8d715ad6`, including corrective implementation, full tests,
`prek run -a`, and a commit. The working tree began clean. Review the complete
feature relative to `140c0f2f`, retaining the user's explicit helper revision:
no Cancel button, clear gesture instructions, and readable styling.

- [x] Independently review correctness, regressions, security, lifecycle,
      compatibility, tests, and complexity across the full feature.
- [x] Perform a separate numerical/rendering review and resolve concrete
      findings.
- [x] Implement the reviewed corrective plan with meaningful regression tests.
- [x] Apply the user's helper correction: concise action/meaning rows,
      start/stop wording, compact content-fitted width, and no awkward wrapping
      or Cancel button.
- [x] Add the requested “Distance measurement instructions” header and
      right-side chevron, with accessible collapse/expand and expansion on every
      activation.
- [x] Run the full Python suite and audit GitLab creations and cleanup.
- [x] Run the full JavaScript suite and relevant browser verification.
- [x] Run `prek run -a`, review any formatter changes, and resolve failures.
- [x] Record findings/results and commit the completed change set.

## Execution boundaries

Use the already-running `speleodb_local_django` container at `/app` for every
test. Run Python, frontend, browser, and hook processes sequentially because the
local VM has limited memory. Frontend verification uses one Vitest worker
without increasing timeouts or skipping coverage. Review agents perform static
analysis while the root runs Python; coordinate before launching other checks.

The principal reviewer owns production/test corrections. A second reviewer
independently examines geometry, formatting, and renderer lifecycle without
editing files. Root owns integration review, documentation, full verification,
GitLab audit, and commit. No backend or GitLab-fixture change is presumed
necessary; investigate concrete failures before expanding scope.

## Findings and review

The separate numerical/rendering reviewer found no actionable findings. The
principal reviewer found a **P2** mouse-preview issue in
`frontend_private/static/private/js/map_viewer/measurement/tool.js:103`: camera
navigation can change the coordinate under a stationary pointer, but the
existing camera callback updates only keyboard drafts. The displayed distance
can therefore disagree with the measurement committed by the next click. The
corrective plan retains the current mouse screen point and re-picks it on camera
movement, with explicit invalidation on leave, cancellation, dialog suspension,
and input-mode changes. Pointer-anchored wheel zoom may preserve the target;
camera changes that alter the projection expose the mismatch.

A second **P2** concerns entity-drag ownership in
`frontend_private/static/private/js/map_viewer/map/interactions.js:229` and its
private-entrypoint activation hooks. Holding the mouse on a writable entity,
activating the ruler with the keyboard, and releasing the mouse while the ruler
is active bypasses the old drag cleanup. After turning the ruler off, ordinary
pointer movement can resume that stale drag and a later release can open a
mutation confirmation. The corrective plan centralizes cancellation of the
pending drag before either tool takes ownership: restore transient position,
color, feedback, and original map handlers; clear all drag state; invoke no
persistence/drag-end callbacks. Permission rules remain unchanged.

The user further requested start/stop wording instead of point A/B, a wider
helper, and concise action/meaning rows instead of prose. This is included in
the authorized correction and responsive/browser verification.

## Verification record

- Full JavaScript suite: **1,323 passed across 85 files**, using one worker in
  the existing application container. Eight new cases cover camera preview
  consistency, canceled/left-canvas previews, pending/moved entity handoffs, and
  normal drag completion with original enabled/disabled camera handlers.
- First full Python attempt was interrupted with **exit 137** during the proxy
  module, after reaching 72%; it has no final test result. The application
  container had restarted by inspection, but the exit's cause was not
  established. Run `b07e6741923644b2a83e920a5ac96f87` recovered from its durable
  ledger: **8 creations / 9 POSTs**, zero violations or unresolved outcomes, all
  eight exact allocated repositories verified marked for deletion. Original
  ledger and pre-cleanup exports remain preserved alongside explicit
  interrupted-run status. Recovery used existing lifecycle APIs and never
  performed group-wide cleanup.

Latest UI correction: remove the “Move pointer” and “Scroll: Zoom” rows and
reduce the helper width to fit the remaining concise gestures. Preserve preview
behavior and the exact “Cancel measurement” label.

## Collapsible helper correction

The user requested the exact title “Distance measurement instructions” and a
right-hand chevron that collapses the helper, expanded by default on feature
activation. Use one full-width native header button with `aria-expanded` and
`aria-controls`, retaining the visible header while hiding the gesture list.
Header interaction must not place map endpoints. Recalculate the existing layout
when toggled so the keyboard reticle respects the actual visible panel. Reset to
expanded whenever measurement mode is activated, without persistence or extra
state beyond this control. Verify mouse and keyboard toggling, no unintended map
click, reactivation reset, and narrow/fullscreen layouts in the real browser.

The independent helper review accepted the collapse semantics and identified a
small header target, corrected to 24px desktop and 44px coarse pointer. Manual
browser inspection also caught overflow in the 320px keyboard gesture table;
responsive stacking and explicit browser overflow assertions are required before
final acceptance. Desktop expanded/collapsed screenshots already verify the
exact title, chevron, compact fit, and single-line mouse action rows.

Final copy/structure correction: restore the horizontal divider above the
exit/clear row and use “Ruler icon” instead of “Click ruler”. Keep the explicit
keyboard shortcut in keyboard mode and the existing clear-all/exit behavior.

## Final browser acceptance

The final authenticated Chromium run passed against the clean Django-served Vite
build, private `main-BRxpfZC7.js` and public `gis_view_main-COAi-cF1.js`, with
all 88 registry entries present. No runtime errors were observed. The watcher
restarted with the recreated container and was stopped before the clean build;
generated assets remain ignored.

Verified the exact title “Distance measurement instructions”, compact desktop
single-line text, right chevron, restored full-width divider, and “Ruler icon”.
Mouse instructions contain only left-click, left-drag, right-click/Escape, and
exit/clear. Header mouse, Enter, and touch toggles preserve measurements and
reactivation expands instructions. The native header has 24px/44px minimum
pointer targets. At widths up to 480px, stacked action/meaning groups avoid
squeezed columns without shrinking type. Explicit cell-overflow checks pass for
320px/390px mouse, keyboard, and touch layouts; the keyboard reticle remains
visible in 844×390 landscape with compact vertical padding.

The same run covered stationary-pointer preview during camera changes, multiple
pairs, right-click/Escape, mouse pan, native touch tap/pan/pinch/cancel,
keyboard, settings/dialogs, geometry-editor ownership, source changes, real
style reload, globe edges, fullscreen, 200% equivalent sizing, 100 completed
measurements, and live-readout visibility while the pointer moves.
Expanded/collapsed desktop and narrow-screen screenshots were inspected
manually. Browser artifacts are in `.artifacts/map-measurement/`; log is
`/tmp/speleodb-ruler-second-browser.log`.

## Full Python result

The serial retry passed: **4,920 passed, 181 skipped** in 595.84 seconds. Run
`c43c7841572e4f55a89507d35b516245` recorded **9 creations / 10 POSTs**, zero
violations and no unresolved creations. Root inspected the summary and 54 audit
events. A separate reviewer then independently verified all nine exact
repository IDs as marked for deletion through read-only SDK calls, including all
four canonical allocations. Evidence is preserved in that run's
`readonly-cleanup-verification.json`; no remote mutations or ledger edits were
needed. The interrupted earlier run remains separately documented above.

## Final JavaScript result

All **1,328 tests across 85 files passed** with one worker, including 29
real-module measurement-tool tests. A test-only fixture initially assigned the
read-only `Config.projects` getter; its failing teardown prevented viewport
cleanup and cascaded through that file. The fixture now saves/restores
`Config._projects`, matching the existing permission tests. The focused file and
then the full suite passed without production changes or weakened
assertions/timeouts.

Thirteen added cases cover camera-preview consistency, preview invalidation,
entity-drag handoff and normal completion with original handler states, all
station/cylinder/lead rollback branches, header state/gesture ownership, and
keyboard-target relayout. Final log:
`/tmp/speleodb-ruler-second-js-verified.log`.

## Hooks and final review

The first full `prek run -a` passed all code, security, type, template, URL,
lint, and clean-build checks. Its Markdown formatter changed only line
wrapping/table alignment; root reviewed those edits before the final all-hook
rerun. The recreated container required restoring Git's trusted `/app` workspace
setting before hook execution. No hook was skipped or weakened.

The two P2 findings and the helper accessibility/responsive findings are
resolved. No permission rules, depth rescans, backend interfaces, package
dependencies, or public measurement controls were added. Both viewer entrypoints
and the complete 88-entry Vite registry remain valid. HTML-producing changes use
trusted static SVG or textContent, with no user-data interpolation. The final
change set is ready for the authorized follow-up commit after the final hook run
succeeds.
