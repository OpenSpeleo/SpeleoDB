# GIS Geometry editor adversarial review

- [x] Prove failures with focused gesture and keyboard regression tests.
- [x] Reset drag click suppression on the next pointer gesture, preserving
      suppression of the drag's own click.
- [x] Finish an active drag before applying draft commands so undo restores a
      coherent snapshot.
- [x] Cancel vertex drags when a second touch starts a map gesture.
- [x] Preserve native Enter activation and navigation focus for controls, and
      GPS updates at the vertex limit.
- [x] Run the focused editor, geometry, interaction, and camera tests in the
      application container.

Plan review: keep the existing shared draft commands and event dispatcher; make
the corrections at editor gesture boundaries without introducing timers or new
configuration. Leave full-suite verification and the final commit to the root
review task.

## Review results

Confirmed five failures before their fixes: a fresh map click swallowed after a
drag, undo overwritten by the unfinished drag, Enter hijacking native control
activation, disabled GPS submission at the vertex cap, and pinch gestures moving
vertices. Added coverage for retaining keyboard focus in vertex navigation.

All 91 tests in the editor, geometry validation, geometry camera, and map
interaction suites passed in `speleodb_local_django`. Camera and geometry
validation required no additional changes. Root review owns final full-suite and
pre-commit results.
