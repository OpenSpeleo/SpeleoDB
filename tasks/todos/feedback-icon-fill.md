# Feedback navigation icon

- [x] Identify the dark fill: the main sidebar's paper-plane SVG defaults to
      black.
- [x] Set an explicit transparent fill and align SVG stroke/color ownership with
      neighboring icons.
- [x] Run container frontend tests, template checks, and a clean production
      build.
- [x] Record results and document the icon styling rule.

## Review

The paper-plane outline now has no interior fill. SVG-level classes preserve its
existing dimensions, stroke weight, and active/inactive colors. Container
JavaScript tests, template formatting/lint, and clean Vite build passed;
`git diff --check` passed. Browser visual verification was not performed.
