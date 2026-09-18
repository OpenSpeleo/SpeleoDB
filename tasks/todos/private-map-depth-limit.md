# Private map depth limit

## Design and implementation plan

- [x] Add a collapsed Depth limit control directly beneath Color mode, visible
      only when Depth is selected in the private viewer.
- [x] Use an optional positive numeric limit and compact meters/feet selector.
      Preserve physical depth during unit changes; blank restores the full
      visible-project range. Validate locally and apply numeric changes on
      commit, not every keystroke.
- [x] Store the canonical limit in feet alongside display preferences; use the
      selected unit for legend and cursor labels. Private persistence must not
      affect public viewers.
- [x] Derive one effective domain from cached visible-project domains and the
      optional fixed maximum. Keep all-hidden/no-depth N/A behavior, saturate
      colors and displayed depth at the limit, and preserve raw source values.
- [x] Cover project/country visibility, delayed project loading, reload, reset,
      unit conversion, invalid values, legacy preferences, public isolation,
      colors, hover, and interaction cost with focused regression tests.
- [x] Review with independent specialists, run container tests/lint/build and
      inspect the live responsive UI. Document architecture and verification.

## Performance contract

Compute per-project depth domains only when ingesting GeoJSON. Limit changes and
visibility toggles merge cached project domains and update paint expressions;
they never rescan feature data or rebuild map sources. Hover clamps one rendered
feature in constant time. A configured maximum stays fixed as visibility
changes; no visible depth data still yields N/A.

## Results

- Implemented the private disclosure, validated numeric commits, unit toggle,
  persistent canonical limit, shared effective scale and capped depth readings.
- Full frontend suite: 1,471 tests passed across 89 files inside the application
  container. Includes private/public entrypoint and production asset contracts.
- Settings label correction to **Full range**: all 23 Settings tests pass.
- Production build and JavaScript lint passed. Live Chromium verified desktop,
  390px and 320px mobile layouts, real legend output, unit conversion, invalid
  and incomplete input, Close/Escape event ordering, reload persistence and
  reset.
- Adversarial review found and corrected a country-gate ordering defect. Added
  real panel integration coverage and a public-entrypoint isolation regression.
  No actionable review findings remain.
- Bounded performance regression passed: 20,000 lines, 100 limit/unit/visibility
  cycles, no feature rescans, extra downloads, source rebuilds or source
  mutations.
- Full `prek run -a` passed after the review corrections. Final checks include
  the formatted documentation and new test files.

## Review

Independent review checked validation and native event ordering, private/public
preference isolation, visibility gates, shared depth-domain ownership, cursor
cleanup, and performance. The full adversarial pass then found and fixed the
country-gate ordering issue described below; no actionable findings remain.
Browser verification covered committing by Close, changing units with an active
draft, and Escape with an incomplete numeric value, in addition to the automated
DOM tests.

Final copy uses **Full range** and **Reset to Full Depth Range**. The collapsed
row has no active highlight. The expanded setting explains how an unusually deep
cave can reduce color detail in shallower passages. Final Chromium checks passed
with this copy and styling, including the computed collapsed background/border.

## Adversarial review correction

- [x] Identify the country-gate ordering defect: an individual toggle recomputed
      the depth domain before the panel restored its hidden country gate,
      leaving a visible range for hidden projects instead of N/A.
- [x] Review the correction for scope and cost: pass the final effective
      visibility into the existing Layers toggle so preference storage, map
      visibility, domain events and repaint happen once. Keep two-argument
      callers compatible and avoid adding a second recomputation in the panel.
- [x] Implement the optional effective-visibility override and remove the
      panel's superseded second visibility update.
- [x] Cover real panel/Layer integration for toggles inside a hidden country,
      all-hidden N/A, another visible country, clearing the cap and revealing
      the country again. Assert only the final domain is emitted.
- [x] Run the final container tests and hooks after the correction.

Final live Chromium verification also toggled country gates and individual
projects through the rendered panel: hidden countries keep N/A, and revealing
countries restores the fixed scale. Served manifest entry:
`assets/controller-private-map-CRqviWGZ.js`. No browser errors were reported.
