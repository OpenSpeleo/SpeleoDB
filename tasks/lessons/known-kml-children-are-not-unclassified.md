# Known KML children are not unclassified constructs

## Correction

A capability scanner classified every KML-namespace local name that the vector
compiler did not consume directly as an “unclassified construct.” On a normal
Google Earth export this mislabeled standard children such as `latitude`,
`longitude`, `heading`, `range`, `when`, and `listItemType`, duplicating the
already-correct warning for their preserved parent constructs.

## Rule

- Keep separate sets for rendered constructs, intentionally preserved
  constructs, known structural/property children, genuinely unknown names in a
  recognized KML namespace, and foreign-namespace extensions.
- A known child of a classified construct may be recorded in detailed capability
  metadata, but must not generate an “unknown” or “unclassified” warning merely
  because phase-one rendering does not consume it directly.
- Compatibility summaries should identify independent degradation decisions, not
  restate every descendant of an already-reported unsupported parent.
- Regression fixtures must assert warning codes and contexts as well as geometry
  counts; correct geometry does not excuse misleading diagnostics.
