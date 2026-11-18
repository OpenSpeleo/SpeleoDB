# Map Viewer Depth Coloring

For cache ownership, private limits, and validation, see
[Depth domain reactivity](depth-domain-reactivity.md).

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

The private viewer additionally offers a collapsed **Depth limit** under
Settings → Appearance → By Depth. A positive maximum fixes colors and displayed
depths to 0–X in meters or feet; blank restores the full visible-project range.
The limit survives project/country toggles and late loads, while no visible
depth data still shows N/A. Raw source depths are never modified. Public maps
retain automatic scaling and do not read private depth preferences. See the
expanded architecture document above for validation, persistence, conversion,
and performance contracts.

Depth legend and cursor behavior is centralized in:

- `frontend_private/static/private/ts/map_viewer/components/depth_legend.ts`

## Complexity

| Operation                   | Cost                                                       |
| --------------------------- | ---------------------------------------------------------- |
| GeoJSON load                | Feature/coordinate traversal and a per-project cache write |
| Project toggle (depth mode) | O(active projects), without feature traversal              |
| Additional domain storage   | One domain object per project plus the merged domain       |
