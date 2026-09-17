# GIS Geometry second frontend review

- [x] Re-read the completed feature and prior review fixes from commit
      `ed9de067`, including management forms, shared rendering, and map state.
- [x] Reproduce and review the corrective plan for a stale detail-request
      failure overriding a newer accepted save.
- [x] Correct the asynchronous failure boundary using existing cache identity,
      with no additional state-management framework.
- [x] Test delayed failures after save/refresh, subsequent explicit hiding, and
      ordinary failure synchronization in the existing container.
- [x] Complete remaining independent review and report verification.

## Finding and corrective plan

**P2 — Stale failure overwrites newer visibility:** in
`map_viewer/map/layers.js`, a pending Show request may fail after an independent
editor fetch and save succeeds. The catch unconditionally turns the visibility
state off while leaving the accepted saved overlay visible. Reproduction in the
application container returned `{toggle: false, rendered: "visible"}`. A later
style reload then omits the geometry despite the successful save.

Move the local record reference outside the try block. If failure occurs after
another operation replaced the cached record, retain the latest explicit
visibility. Otherwise turn both state and rendered visibility off. Test both
Save and Refresh replacement, and explicitly test hiding after a save so a stale
failure never resurrects it. The primary reviewer approved this narrow plan
before implementation.

## Verification

The application container passed **32 tests** across the geometry layer-state
and panel suites, including four new regressions for the finding. Reviewed
management JSON form atomicity/error retention, shared form compatibility,
listing HTML/URL/color escaping, vector renderer parity for GIS Layers,
private-only initialization, toolbar/menu/template requirements, and geometry
style-reset restoration. No additional actionable findings were established.
