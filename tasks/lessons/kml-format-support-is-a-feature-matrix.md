# KML/KMZ Support Is a Feature Matrix

When a map-file request mentions KML/KMZ or Google Earth, establish the desired
fidelity before selecting a converter. Supporting the extension can mean only
Placemark geometry, while Google Earth also treats KML as a hierarchical scene,
asset package, time model, and Region/NetworkLink loading protocol.

Rules to keep:

- Inventory KML constructs and malformed-producer behavior before proposing a
  parser.
- Separate common 2-D vector compatibility from Google Earth scene/runtime
  parity.
- Never use successful feature counts alone as fidelity evidence; verify rings,
  geometry parts, styles, assets, hierarchy, and content after parse errors.
- Do not claim universal support when the renderer cannot express altitude,
  models, PhotoOverlays, Tours, or network refresh semantics.
- Prefer an explicit supported/degraded/unsupported report over silent loss.
- For large KML, distinguish parsing memory from rendering scale. Arbitrary
  feature-count splitting does not fix huge individual geometries; use spatial
  LOD/tiling when necessary.

Origin: the requested target was clarified from KML/KMZ/GeoJSON geometry loading
to anything Google Earth can load. The supplied KMZ also demonstrated that a
tolerant parser could report all features while a different parser lost 91
interior rings, proving that format-level success is not fidelity.
