# KML/KMZ map import

## Approved plan

- [x] Extend the shared KML/KMZ compiler with bounded analysis, point-only
      landmark candidates, and compatibility diagnostics.
- [x] Add read-only inspection; reuse existing confirmation endpoints and
      transactional publication.
- [x] Rebuild the import dialog around explicit Placemarks / Map Overlay intent,
      adaptive forms, inline review, and persistent results.
- [x] Integrate affected-data refresh and explicit Show on map without changing
      existing visibility or camera automatically.
- [x] Cover parser/API, dialog lifecycle, permissions, rollback, and map
      integration with regression tests.
- [x] Document design, interfaces, supported content, limitations, and lessons.
- [x] Complete independent adversarial review and address actionable findings.
- [x] Complete verification under the final agreed scope and commit the work.

## Boundaries

One KML/KMZ file creates exactly one GIS layer in Map Overlay mode. Placemarks
creates only landmarks. There is no mixed mode, folder splitting, job, polling,
or temporary import storage. Original overlay sources remain intact. Existing
GPX import behavior and direct GeoJSON uploads remain compatible.

## GPX result navigation

- [x] Explain tracks and landmarks as independent GPX outcomes, put file
      selection first, and label the collection destination for landmarks only.

- [x] Enable Show on map for GPX results with created tracks or landmarks.
- [x] Reveal only the returned track IDs and fit the imported extent through
      shared map navigation. Keep failed display separate from successful
      import.
- [x] Return created GPX track IDs and new-content bounds from the API, and add
      regression coverage. Final test execution has resumed at the user’s
      request.

## Review and results

### Design refinement requested September 17

- [x] Align remaining GPX modal copy, design docs, and UI test descriptions with
      landmarks terminology; balance the moved collection help spacing.

- [x] Present export help as a styled, numbered three-step guide with a
      mode-specific first step and highlighted menu/format labels.

- [x] Move shared Google Earth export help above the destination field and
      clarify which content to select for Placemarks versus Map Overlay.

- [x] Replace the separate selector with clickable choice cards and a Change
      action; remove Points of interest from the Placemarks examples.

- [x] Rename the modal and modes using the requested product language.
- [x] Show two concise outcome explanations before mode selection; reveal the
      form only after selection and remove the explanations.
- [x] Strengthen visual hierarchy with purposeful color, icons, selected states,
      and a clearly recognizable native collection dropdown.
- [x] Update design documentation and lessons for the approved visual
      refinements.

Final adversarial review and verification resumed after user approval of the UI.
Backend and frontend reviewers independently examine the full change; corrective
work includes hidden-mode feedback, active-display teardown, accessible choice
cards, KML feature ancestry, and archive allocation bounds. Full checks run
serially inside the existing application container.

- [x] Complete review corrections and regression coverage.
- [x] Full JavaScript suite: 87 files, 1,374 tests passed.
- [x] Full Python suite: 4,981 passed, 181 skipped (12m 19s). GitLab audit:
      nine repositories, ten creation POSTs, zero violations or unresolved
      allocations; all nine repositories marked for deletion during cleanup.
- [x] User ran `prek`; no duplicate run, per the final instruction.
- [x] Earlier live KML/KMZ imports and desktop/mobile visual checks completed.
      Additional browser rerun omitted per the final instruction to finish the
      running tests and commit immediately. GPX navigation has API/unit coverage.
- [x] Commit all approved changes.

### Adversarial review corrections

- Prevent dialog teardown from resetting an active Show operation; share the
  busy/showing guard with dismissal.
- Keep late KML inspection progress/errors out of the mode chooser and associate
  each choice card with its accessible description.
- Do not cache GPS data until layer installation succeeds, so display retries
  actually retry installation.
- Validate finite WGS84 GPX track positions before publication; otherwise bounds
  serialization could fail after rows/files had been committed.
- Restrict KML feature ancestry and bound actual KMZ directory records before
  eager archive-object allocation.
- Unwrap crossing bounds for Mapbox camera fitting, preserving narrow extents
  across the international date line.

Focused verification: 44 parser cases and six GPX cases passed. KML API tests
pass (13 cases) after matching the authentication tests to the non-atomic
request lifecycle. These focused runs provisioned no GitLab repositories.

Full Python audit: `.artifacts/gitlab/607b08e3e7524fb586fe0de30dc85f82/`.
Clean Vite builds passed throughout; the final hook run was performed by the
user, who requested finishing the running tests and committing immediately.
