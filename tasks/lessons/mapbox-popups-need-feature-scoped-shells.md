# Mapbox popups need feature-scoped shells

## Correction

Putting safe text inside `setDOMContent()` is necessary but does not produce a
finished viewer experience. The default light Mapbox popup shell looked alien
inside the dark GIS viewer, while the unstructured title and description made
large imported properties difficult to scan.

## Rule

- Treat a popup as two owned surfaces: the semantic DOM content and the Mapbox
  shell around it (content, tip, close control, focus, width, and overflow).
- Pass a feature-specific `className` to `mapboxgl.Popup` and scope every Mapbox
  selector beneath it. Never globally restyle `.mapboxgl-popup-content`.
- Build user-derived content with DOM nodes and `textContent`; never render raw
  KML descriptions or ExtendedData as HTML.
- Allowlist useful metadata, bound row counts and text length, and do not turn
  arbitrary values into links, CSS, or markup.
- Test both content safety and CSS selector scope.
- Put `overscroll-behavior` on the element that actually scrolls and stop
  wheel/touch propagation at that boundary. Visual overflow alone does not
  prevent the page from chaining scroll or Mapbox from treating wheel input as
  zoom.
- Keep fixed popup hierarchy outside the scroll viewport: the header and a
  compact, ellipsized metadata footer must not move or become secondary scroll
  regions when a description is long.
- Do not rely on native scrollbar chrome as the only overflow signal; macOS and
  other platforms may auto-hide it. Measure the actual middle viewport and show
  a feature-owned rail/thumb only while it overflows. The indicator can remain
  pointer-transparent while native wheel, touch, and keyboard scrolling own the
  interaction.
- Update the thumb on scroll and resize, remove external listeners when the
  popup closes, and leave short popups undecorated.
