# Resolve visibility before publishing depth changes

Applying a project toggle and then restoring a hidden country gate left the map
hidden but its depth domain stale. The layer operation had already recomputed
and published the range using the individual preference alone.

Resolve individual preference plus country gate before the shared visibility
operation emits domain changes. Keep persistence of the individual toggle
separate from the effective visibility argument. Test through the real
project-panel entry point as well as layer helpers; directly setting
effective-state maps cannot catch the ordering bug.
