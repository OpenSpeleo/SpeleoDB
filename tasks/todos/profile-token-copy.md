# Profile token copy button

Follow-up plan: apply the requested info style using the existing sky-blue
button colors, then rerun container frontend checks and the production build.

- [x] Apply sky-blue info styling with white text and a darker hover state.
- [x] Recheck: 1,191 JavaScript tests, template formatting/lint, production
      build, and `git diff --check` passed after the style change.

- [x] Inspect the token page, shared copy controller, and repository guidance.
- [x] Add a right-side copy button using the shared controller, including input
      value support.
- [x] Verify clipboard success/fallback/failure and existing text sources; run
      container tests, lint, and production build.
- [x] Document the behavior and record verification results.

Plan: preserve the existing token field and refresh flow. Use the existing
copy-token route controller for clipboard access and temporary feedback, with
input value support so the token does not need to be duplicated in the DOM.

## Review

The Copy button uses the established control styling and shared clipboard
handling, with an accessible label and live feedback. Existing integration-page
text sources retain their behavior. No backend or token refresh changes.

Verified in `speleodb_local_django`: all 1,191 JavaScript tests (73 files),
JavaScript lint, clean production build, and template formatting/lint passed.
Six focused regressions exercise the page configuration and clipboard paths.
`git diff --check` passed. Browser visual verification was not performed.
