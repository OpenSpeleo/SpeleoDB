# KML import intent and layer boundaries

## Corrections

The user rejected combined landmark/layer output and automatic folder splitting.
Users choose **Placemarks** or **Map Overlay** by selecting one of two
explanation cards. Map Overlay mode always creates one GIS Layer per KML/KMZ
file.

## Rules

- Explain outcomes before product terminology; a KML point may be an area label.
- Inspect content automatically, but never infer intent or silently switch it.
- Keep folder content and the original source together in one overlay.
- Do not add a combined mode, split-layer workflow, generated KML exporter, or
  source-sharing model when the selected product scope does not need them.
- Keep synchronous inspection/confirmation and existing publication boundaries;
  background jobs require an explicit requirement to continue after navigation.
- Preserve results until dismissal and distinguish map-refresh failure from
  import failure so a retry cannot duplicate successful publication.

## Visual hierarchy correction

- Use the requested product labels: Placemarks and Map Overlay.
- Explain both outcomes before selection, then replace the explanations with the
  relevant form. Do not show an inactive upload area before the decision.
- Native selects still need an obvious dropdown affordance; never style them as
  indistinguishable text inputs.
- Use deliberate accent colors, recognizable icons, and distinct surface levels
  to guide attention. A dark background and thin borders alone are insufficient.

- When explanation cards already describe the available choices, make the cards
  themselves selectable instead of adding a redundant selector. Keep a compact
  Change action after selection, and preserve keyboard focus across the swap.

- Put file preparation instructions before the destination fields, where users
  need them. Share common export steps and explain only the mode-specific
  selection differences.

- Present procedural help as short numbered steps with visible action labels,
  not dense paragraphs. Adapt the content to the chosen mode instead of making
  users filter instructions for both modes.

- Import completion actions must be consistent across formats. GPX needs the
  same explicit Show on map action as KML/KMZ; return created entity IDs and
  bounds from publication instead of inferring them from list differences.

- For multi-output imports, describe each output independently. Put file
  selection before destination settings that apply to only one output, and label
  those settings with their scope (landmarks only).

- Use landmarks consistently in the GPX modal, including its headline. Reserve
  waypoint terminology for the actual GPX format/parser, and explain the mapping
  in engineering docs. Preserve user copy edits and placement when refining CSS.

- Run full Python/GitLab tests, Vitest, hooks, and browser verification serially
  in the shared development VM. Concurrent heavy checks can starve GitLab and
  make infrastructure timeouts obscure real regressions.
