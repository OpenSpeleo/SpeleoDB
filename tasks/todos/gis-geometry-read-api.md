# GIS Geometry read-only integration specification

- [x] Inspect model, shared contract, serializers, GET views, authentication,
      permissions, rendering constants, and existing tests.
- [x] Write a standalone agent-facing specification for the feature and all
      three GET endpoints, with exact fields, examples, errors, and client
      behavior.
- [x] Include transparency as explicit content and named rendering constants;
      distinguish opacity from transparency and API fields from client
      constants.
- [x] Correct the stale documentation index and link the new specification.
- [x] Verify examples/claims against implementation and check Markdown format.

The user requests documentation for another agent, restricted to read access. Do
not document or implement mutation endpoints. Rendering constants already exist
in the shared map configuration; reuse their names and values rather than adding
a per-record setting or duplicate policy source.

## Verification

An independent backend reviewer verified all GET routes, status behavior,
ordering, fields, authentication, and revision/access caching semantics.
Container execution validated all six JSON examples against the actual
serializers and geometry validator. An unsaved serializer probe verified the
timestamp offsets, string permission levels, and zero-area line example; an
anonymous GET confirmed the documented 403 response. No application data or
runtime code changed. Markdown formatting and diff checks passed.
