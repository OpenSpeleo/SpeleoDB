# Unify the asset pipeline at the compiler boundary

## Correction

Combining public/private Tailwind configuration or emitted CSS does not unify
frontend tooling while separate JavaScript compilers, watchers, generated
paths, and template loading mechanics remain. “Unified” must be evaluated at
the dependency-graph and deployment boundary, not by counting stylesheets.

## Rule

When consolidation is the goal, inventory every compiler, watcher, entry,
output, template reference, deployment hook, and runtime bridge first. Prefer
one graph and manifest with route-sized outputs over either parallel pipelines
or a monolithic payload. The backend may remain the sole server: compiler
unification does not require adopting the compiler's dev server or HTML layer.

Preserve route boundaries for cascade and network performance, but make those
boundaries explicit registry entries in the same graph. Replace loading-only
globals and executable inline handlers with imports, inert structured context,
and delegated listeners. Prove the result through clean builds, manifest
contracts, watcher invalidation, live route behavior, and served hashes.

When the disk-build watcher shares a container with Django, keep its stdout and
stderr attached to the container console and disable terminal clearing. An
otherwise-correct background watcher can make Django logs appear to vanish when
its rebuild output clears the shared screen.
