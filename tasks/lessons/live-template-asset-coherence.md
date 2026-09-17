# Keep the running page coherent during frontend changes

The private map redesign updated the live Django template before its new Vite
CSS and JavaScript were built. No watcher was running, so the user received new
button markup with the old styles and handlers and reported broken controls.

- Check whether the root Vite disk-build watcher is running before editing live
  templates together with first-party styles or controllers.
- Keep build output synchronized during implementation, or isolate incomplete
  template changes from the user-facing checkout until the companion assets can
  be built together.
- Prioritize a clean build and actual authenticated browser smoke test as soon
  as an integrated UI slice exists; do not defer all browser checks until after
  documentation or the complete test matrix.
- Confirm served manifest hashes and all primary button actions before reporting
  a live interface as implemented. Unit tests alone do not prove asset
  coherence.
- Stop the watcher and clean-build again before final visual evidence.
