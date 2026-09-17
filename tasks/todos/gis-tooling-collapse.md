# Collapsible GIS Tooling navigation

Icon follow-up: add the user-supplied map/layers SVG to the shared summary,
matching 24px sidebar icon sizing, slate color, and 12px label spacing; verify
template checks and frontend regressions.

Label follow-up: the final requested name is **GIS Tooling**. Indented the
nested list with a subtle left guide and allowed child labels to wrap on narrow
screens. Updated controller/template tests and current navigation documentation.

Width follow-up: use the requested 290px sidebar width for both layouts, capped
to available width. Translate the closed mobile drawer by its full width. Verify
that GIS labels fit on one line and the mobile drawer fully closes.

Width verification passed at 1440/390/320px: 290px sidebar, all nine labels on
one line, and closed mobile drawer fully offscreen. Header-spacing follow-up
replaces `mb-10 mt-3` with `my-3` and updates matching mobile logo/spacing
selectors. After the spacing change, all 1,197 JavaScript tests, template
checks, clean production build, and `git diff --check` passed.

Final icon/indent verification: all 1,197 JavaScript tests, 68 template
regression tests, template formatting/lint, and clean build passed. Chromium
confirmed the 24px supplied icon, label/chevron fit, 16px list indent and 1px
guide, all nine labels without horizontal overflow, and native/automatic
toggling at 1440, 390, and 320px. Current served stylesheet:
`style-app-qxTFtkh3.css`.

- [x] Inspect the shared sidebar, route highlighting, and controller
      conventions.
- [x] Move GIS Survey Map immediately after Survey Tools, outside the GIS group.
- [x] Add a native GIS Tooling disclosure, collapsed by default and opened by
      its current-page link.
- [x] Give the standalone map link a subtle blue tint, thin border, and brighter
      icon per follow-up request.
- [x] Update route/interaction tests, docs, and superseded ordering guidance.
- [x] Run container checks and browser verification at desktop/mobile widths;
      independently review.

Plan: keep one shared sidebar. Use native details/summary for accessible pointer
and keyboard toggling. A small Vite controller opens the group when one of its
links is marked aria-current by existing server route highlighting, avoiding a
second route registry. No saved expansion preference: every navigation starts
closed unless the destination belongs to GIS Tooling.

## Review

Independent review found no blocking issues. Added the missing cylinder hydro
and visual watchlist routes to their existing highlighting predicate so those
pages auto-expand too. All nine grouped route families use the same current-page
marker; no second route registry or persistent expansion preference was added.

The user caught a live Unknown Vite logical entry error during implementation.
Built the new entry and triggered development-server autoreload: the logical
registry is cached for the Django process lifetime. Confirmed authenticated
`/private/landmark-collections/` returned HTTP 200 from the running server.
Recorded the registry/build ordering lesson.

Container verification: 178 targeted Python tests, all 1,197 JavaScript tests,
JavaScript lint, template formatting/lint, Ruff, focused mypy, clean production
build, and `git diff --check` passed. GitLab audit: zero creations, creation
POSTs, violations, or unresolved outcomes; no remote cleanup required.

Live Chromium checks passed at desktop (1440px) and mobile (390px): default
collapse on the profile, automatic expansion on landmark collections, manual
click/Enter/Space toggles, and map placement outside the group after Survey
Tools. The final map accent uses the existing 30%-opacity sky border token and
10%-opacity blue background. A visual check caught and corrected undefined
border tokens before completion. Final clean build and template lint passed.
Verified served assets: `style-app-D62muhE_.css` and
`controller-private-navigation-CCKQAp0g.js`.
