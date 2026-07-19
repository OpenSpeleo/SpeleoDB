# Agent Documentation Index

This directory contains LLM/agent-focused technical documentation.

Unlike product docs, these files prioritize:

- engineering intent and invariants
- architecture boundaries and extension points
- expected test coverage
- performance constraints and anti-patterns

## Topics

### Architecture and System Design

- `local-object-storage.md`
  - local RustFS ownership, automatic `.env`/GitLab/bucket/superuser bootstrap,
    isolated Compose projects, signed URL flow, production boundaries,
    diagnostics, and regression coverage
- `map-viewer/architecture.md`
  - module dependency graph, private vs public comparison, initialization
    sequences, state management, layer system, event system, build pipeline
- `map-viewer/data-flow.md`
  - GeoJSON loading pipeline, CRUD operation flows, refresh event system,
    caching strategies

### Feature Documentation

- `api-docs-access.md`
  - user-level API Docs/API Schema menu visibility flag, admin ownership, and
    permission boundaries
- `map-viewer/features.md`
  - station/landmark/exploration lead/GPS track/cylinder management,
    drag-and-drop, context menu, component library
- `map-viewer/api-reference.md`
  - frontend API client, backend endpoint inventory, OGC API endpoints,
    authentication model
- `map-viewer/design-requirements.md`
  - canonical map viewer feature contracts and guardrails

### Security

- `xss-protection.md`
  - render-side HTML escaping strategy, `Utils.escapeHtml` / `Utils.safeHtml` /
    `Utils.raw` API, attribute-context escaping, jQuery `.html()` patterns,
    inline `escapeHtml` alignment, CSS color validation

### Specialized Topics

- `local-debugging.md`
  - always-available Django Debug Toolbar with every panel disabled by default,
    panel activation, performance rationale, and verification
- `monorepo-native-dependencies.md`
  - monorepo-only Rust toolchain boundary, editable `openspeleo_core` setup,
    cache invalidation, and standalone-image behavior
- `project-geojson-command.md`
  - management-command modes, Git clone lifecycle, GeoJSON recomputation,
    failure behavior, and performance boundaries
- `map-viewer/depth-domain-reactivity.md`
  - depth color mode architecture, cache model, and performance rationale
- `map-viewer/map_viewer_depth_coloring.md`
  - markdown conversion of `docs/map_viewer_depth_coloring.rst` for agent usage
- `map-viewer/permissions-and-access.md`
  - centralized permission model and scope-routing behavior

### Quality and Testing

- `map-viewer/testing-and-quality.md`
  - frontend test map, validation commands, and regression checklist
- `node-tooling.md`
  - root npm workspace constraints, Node runtime compatibility, install-script
    approval policy, and verification commands
- `tailwind-v4.md`
  - Tailwind 4 build ownership, v3 visual-compatibility layer, source and
    variant contracts, browser floor, and parity-verification requirements

### Coding Rules

- `coding-rules.md`
  - JS constant centralization, Python import ordering, Django ORM rules (hard
    rules, must not be violated)

Repository-wide agent guardrails live at:

- `AGENTS.md`
