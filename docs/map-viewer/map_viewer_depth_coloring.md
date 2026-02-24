# Map Viewer Depth Coloring (Agent Edition)

This file is the Markdown agent-oriented conversion of:

- `docs/map_viewer_depth_coloring.rst`

For the expanded architecture and implementation guidance, see:

- `docs/map-viewer/depth-domain-reactivity.md`

## Overview

Depth coloring uses a two-stage domain model so project visibility toggles stay
reactive with large GeoJSON payloads:

- Stage 1 (load time): each project computes and caches its depth domain.
- Stage 2 (toggle time): only visible project domains are merged.

Applies to both:

- private map viewer (`frontend_private`)
- public GIS view map (`frontend_public`)

## Depth Domain Model

### Per-project cache

When project GeoJSON is loaded or refreshed, the viewer computes one domain for
that project and stores it in:

- `State.projectDepthDomains`

The same processing stamps:

- `depth_val` (canonical raw depth)
- `depth_norm` (legacy hover fallback)

### Active merged domain

When project visibility changes:

1. collect visible project ids
2. read cached per-project domains
3. merge via `mergeDepthDomains(...)` into `State.activeDepthDomain`

No per-feature rescans are needed during toggles.

## UI Behavior

In depth mode:

- visible projects drive line-color expressions and gauge labels
- hide/show immediately recomputes active merged domain
- all projects hidden shows `N/A` in gauge labels

Depth legend and cursor behavior is centralized in:

- `frontend_private/static/private/js/map_viewer/components/depth_legend.js`

## Complexity

| Operation | Before | After |
|---|---|---|
| GeoJSON load | O(total features) | O(total features) + per-project cache write |
| Project toggle (depth mode) | O(active features) | O(active projects) |
| Memory | GeoJSON only | GeoJSON + one domain object per project |

