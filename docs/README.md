# Agent Documentation Index

This directory contains LLM/agent-focused technical documentation.

Unlike product docs, these files prioritize:

- engineering intent and invariants
- architecture boundaries and extension points
- expected test coverage
- performance constraints and anti-patterns

## Topics

### Architecture and System Design

- `map-viewer/architecture.md`
  - module dependency graph, private vs public comparison, initialization
    sequences, state management, layer system, event system, build pipeline
- `map-viewer/data-flow.md`
  - GeoJSON loading pipeline, CRUD operation flows, refresh event system,
    caching strategies

### Feature Documentation

- `map-viewer/features.md`
  - station/landmark/exploration lead/GPS track/cylinder management,
    drag-and-drop, context menu, component library
- `map-viewer/api-reference.md`
  - frontend API client, backend endpoint inventory, OGC API endpoints,
    authentication model
- `map-viewer/design-requirements.md`
  - canonical map viewer feature contracts and guardrails

### Specialized Topics

- `map-viewer/depth-domain-reactivity.md`
  - depth color mode architecture, cache model, and performance rationale
- `map-viewer/map_viewer_depth_coloring.md`
  - markdown conversion of `docs/map_viewer_depth_coloring.rst` for agent usage
- `map-viewer/permissions-and-access.md`
  - centralized permission model and scope-routing behavior

### Quality and Testing

- `map-viewer/testing-and-quality.md`
  - frontend test map, validation commands, and regression checklist

### Coding Rules

- `coding-rules.md`
  - JS constant centralization, Python import ordering, Django ORM rules
    (hard rules, must not be violated)

Repository-wide agent guardrails live at:

- `AGENTS.md`

