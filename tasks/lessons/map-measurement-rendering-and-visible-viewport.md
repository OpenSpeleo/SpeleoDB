# Measure readiness and layout against what the user can see

The private ruler's browser review found issues that isolated map-boundary unit
tests could not expose:

- `map.isStyleLoaded()` includes tile/source loading in the pinned Mapbox
  version. It is not a gate for adding a small runtime overlay. Wait only for
  the style itself, and let measurements render while background tiles load.
  Exercise activation immediately after a basemap change in a real browser.
- Native symbol labels appear after worker processing and glyph loading. GeoJSON
  label properties do not prove visible distance capsules. Wait for native
  rendered label features and inspect settled screenshots, including a moving
  preview.
- Native symbol placement identifies labels by text and anchor, causing
  continuously changing distance labels to fade away during mouse movement. Test
  while the pointer is still moving. Use one native Mapbox Marker for the
  changing readout while keeping completed results in native collision-managed
  layers; do not globally disable every map label's fade.
- Stretchable-image content insets and `icon-text-fit-padding` both contribute
  to capsule size. Give text padding one owner; visually check actual pixels.
- The map may retain a 600px minimum height below a short landscape viewport.
  Responsive control layout must use its intersection with the visual viewport,
  not the map element height alone. Observe resize and scroll as well as map
  bounds; retain the required source/ruler order and usable touch targets.
- Keyboard placement and its crosshair must use the same visible-map center. A
  control fitting on a short screen does not prove that its keyboard target is
  visible. Recompute both on viewport resize/scroll and verify Enter places the
  endpoint at that exact target.
- Project/overlay panels are siblings of the map canvas. Search their actual
  host when computing free instruction space, and account for inline panel
  visibility changes without observing every map animation style mutation.
- In a resource-constrained application container, run full Python, frontend,
  and browser verification sequentially. Await the existing tool session before
  starting another test process; stopping a command must include its owned
  workers. A single Vitest worker can lower memory pressure without skipping
  coverage or increasing timeouts.
