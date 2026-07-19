# Local Debug Instrumentation

## Default Runtime

Django Debug Toolbar remains available throughout local development. Local
settings always add:

- the `debug_toolbar` Django application;
- `DebugToolbarMiddleware`;
- the `__debug__/` URL namespace;
- the SpeleoDB toolbar visibility callback;
- the package's canonical default panel list.

Every canonical default panel is also present in `DISABLE_PANELS`. Django Debug
Toolbar defines this state as disabled but still displayed, so the toolbar shell
remains visible while no panel collects diagnostic data by default.

The project imports the panel list from the installed Debug Toolbar package
instead of copying it. If an upgrade adds another default panel, that panel also
starts disabled automatically.

Expensive panel sub-options also default to off:

- SQL and cache stack traces, including locals;
- SQL prettification;
- project-code capture by the profiling panel;
- template-context capture.

The default exists because panels such as Static Files and Templates can walk
large source trees or process large template contexts. Under Docker Desktop
filesystem and memory pressure, those operations can turn otherwise fast local
requests into multi-second requests. Keeping the toolbar shell does not require
paying the collection cost of panels that remain disabled.

Silk is a separate diagnostic integration. Its request interception and Python/
SQL profiling flags remain disabled in local settings and are not controlled by
Debug Toolbar panel state.

## Enabling a Panel

Use the control in the toolbar UI to enable only the panel needed. The selection
applies to the next request, following Django Debug Toolbar's panel activation
model. No tracked settings edit, private environment variable, or webserver
restart is required.

Disable the panel from the same toolbar control when the investigation is
finished. Avoid enabling Static Files, Templates, SQL, Cache, Signals, or
Profiling ambiently when measuring ordinary page performance.

## Visibility Boundary

The existing `speleodb.debug_toolbar.show_toolbar` callback continues to decide
whether the toolbar shell should be inserted for a request. It preserves the
existing Ariane view exclusion. Panel defaults do not bypass that callback or
make the toolbar available outside local `DEBUG` settings.

## Verification

The focused settings test launches an isolated local-settings process and
checks that:

- the application, middleware, URL route, configuration, and callback exist;
- the canonical panel list is non-empty;
- every configured panel is included in `DISABLE_PANELS`;
- the expensive panel sub-options remain false.

Run it with:

```bash
pytest speleodb/common/tests/test_local_debug_toolbar_settings.py
```

When investigating local latency, benchmark requests only after stopping any
recursive scans or other diagnostic workloads. Compare repeated cold and warm
requests; do not infer allocated memory from Docker's displayed memory ceiling.
