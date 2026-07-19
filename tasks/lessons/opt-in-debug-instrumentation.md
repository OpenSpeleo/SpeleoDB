# Disable Expensive Debug Panels, Not the Toolbar

## Lesson

When a request says to turn off every Debug Toolbar tool, distinguish the
toolbar shell from its diagnostic panels. Removing the application, middleware,
routes, and callback also removes the toolbar UI and is a materially different
behavior.

Repository growth and editor indexing can evict filesystem metadata from cache,
turning an otherwise tolerable per-request file walk into multi-second latency.
Use `DISABLE_PANELS` for default panel state. Disabled panels remain displayed
in the toolbar and can be enabled intentionally for the next request without a
settings edit or server restart.

## Rules

- Preserve the toolbar application, middleware, URLs, callback, and canonical
  panel list when only panel tools should default to off.
- Put every canonical default panel in `DISABLE_PANELS`; import the package list
  instead of maintaining a copied list that can drift after upgrades.
- Disable expensive panel sub-options explicitly when the requirement is for all
  diagnostics to start off.
- Test both the visible integration and the disabled panel set through effective
  Django settings and the URL graph.
- Benchmark with diagnostic workloads stopped; never report measurements that
  overlap a recursive scan or other artificial I/O load.
- Prefer targeted diagnostic activation over permanent per-request profiling.
