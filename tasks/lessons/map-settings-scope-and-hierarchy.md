# Keep map appearance separate from entity management

The first map Settings design mixed appearance, every possible layer gate, and
three manager launchers into a long scrolling dialog. The user's visual review
found management hard to find and outside the expected meaning of Settings.

- Group controls by the user's task, not by which toolbar buttons they replace.
- Keep entity managers directly accessible through a clearly named launcher.
- Prefer compact color controls and essential marker switches over a duplicate
  set of controls for content already managed by map panels.
- Review button widths, colors, and dialog density in the live browser early.
- When removing a preference from the UI, remove or migrate its persisted state
  too: an invisible control must not leave content permanently hidden.
- When moving an existing button into a menu, audit shared stylesheets for old
  ID selectors. The retained Survey Stations ID inherited a 10rem toolbar width
  from `custom.css`, overriding the menu's full-width rows. Verify hover at both
  edges of every row using computed bounds, not only a screenshot at rest.
- Search all frontend test files for retired toolbar classes and accessible-name
  assumptions, including tests owned by neighboring features. The full suite
  found a GIS Geometry view test still splitting the removed authoring wrapper;
  focused Settings/template checks did not include that integration contract.
