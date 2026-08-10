# Vite Controller Globs Must Exclude Tests

SpeleoDB discovers route controllers through `import.meta.glob()` in
`frontend_common/app.js`. A collocated `*.test.js` file also matches a broad
`*.js` pattern and will be emitted into the browser bundle, where Vitest globals
such as `vi` and `describe` do not exist.

Whenever controller discovery or controller tests change:

- keep the negative `!./controllers/*.test.js` glob alongside the positive
  controller glob;
- verify the production asset graph contains no `*.test.js` module;
- run a clean Vite build before browser verification so a stale manifest or
  retained watcher candidate cannot hide the mistake.
