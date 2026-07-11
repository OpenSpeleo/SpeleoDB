# Tailwind CSS v4 Migration Prompt Analysis

## Plan

- [x] Inventory the root Node workspace, Tailwind entrypoints and configs,
      generated outputs, Django templates, JavaScript class generation, CI,
      development, and deployment hooks.
- [x] Catalog repository-specific Tailwind v3 behavior that must remain byte-,
      cascade-, or visually equivalent after upgrading to Tailwind v4.
- [x] Cross-check all relevant v3-to-v4 behavior changes against official
      Tailwind documentation.
- [x] Produce a self-contained principal-engineer execution prompt with explicit
      scope, sequencing, invariants, tests, visual regression loops, and stop
      criteria.
- [x] Re-review the prompt against the repository inventory and record the
      results.

## Review

- Analyzed Tailwind v3.4.19 across both root-managed build pipelines. The
  current unminified public and private baselines are respectively 88,382 and
  116,935 bytes at the analyzed working tree.
- Confirmed 20 public templates, 97 private templates, 47 templates with inline
  style blocks, four public top-level JavaScript sources, six private top-level
  JavaScript sources, and 69 recursively scanned map-viewer JavaScript files.
- Identified source-detection expansion as a concrete v4 risk because the two
  builds intentionally scan different file sets and include some tests while
  excluding other JavaScript subtrees and template-adjacent `.js` files.
- Identified repository-specific coupling to Tailwind v3 internals in
  `frontend_public/static/css/custom.css`,
  `frontend_private/static/private/css/custom.css`,
  `frontend_private/static/private/css/map_viewer.css`, and
  `tailwind_css/private/style.css`.
- Identified the public GIS view as a special cascade case because it loads both
  public and private generated Tailwind styles, followed by private custom and
  map-specific styles.
- Accounted for v4.3.1 CLI packaging, browser floor, source detection,
  JavaScript configuration loading, palette/color-space changes, utility
  renames/removals, Preflight changes, selector changes, variant behavior,
  transforms, cascade layers, plugins, and custom-property differences.
- The delivered prompt requires a preserved v3 reference worktree, deterministic
  CSS and browser baselines, exact source registration, repeated computed-style
  and pixel comparisons across routes/states/viewports, clean-install and
  watcher checks, all repository tests, documentation, and a
  zero-unexplained-difference completion gate.
