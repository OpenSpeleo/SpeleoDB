# Measurement instructions must explain the gestures

The user rejected the initial ruler helper because its abbreviated prompts
assumed users already understood the interaction and its Cancel button added
unwanted UI.

- Remove the separate Cancel button. Desktop draft cancellation uses right-click
  or Escape; the ruler always exits and clears all measurements.
- Say "left-click" explicitly for starting/stopping and "left-drag" for panning.
  Keep these distinct without adding tutorial prose.
- Keep the mouse reference to the four requested actions: left-click, left-drag,
  right-click/Escape, and ruler exit/clear. Preserve pointer preview and scroll
  zoom behavior without separate instruction rows.
- Use readable contrast and clear hierarchy. Verify the instructions remain
  usable on narrow and short screens without covering the keyboard target.
- Write touch and keyboard instructions for the actual input method rather than
  displaying desktop-only gestures on a phone.

## Follow-up correction: scan actions, do not read a tutorial

The user also rejected prose instructions, point A/B terminology, and a narrow
card that caused awkward wrapping.

- Use concise, aligned action/meaning rows: "Left-click: Start / stop",
  "Left-drag: Pan map", and equivalent input-specific rows.
- Refer to starting and stopping a measurement instead of point A and point B.
- Size the helper for its content on desktop and use a deliberate responsive
  layout on small screens. Do not solve wrapping by shrinking readable text.
- Remove explanatory prose that repeats the meaning already conveyed by an
  action label. Keep the complete gesture reference visible and easy to scan.
- Use the explicit action label “Cancel measurement” for right-click and Escape.

- After reducing copy to action rows, fit the card to those rows instead of
  keeping the wider prose layout. The user explicitly removed the “Move pointer”
  row; keep the preview behavior without displaying that instruction.

- The user also removed “Scroll: Zoom” from mouse instructions. Preserve native
  zoom behavior while keeping the mouse card focused on its four requested rows.

- Title the card “Distance measurement instructions”. Let users collapse it
  through a right-hand chevron; keep the header visible and reopen instructions
  on every ruler activation. Use native button semantics and expose the expanded
  state.

- Preserve the horizontal divider above the exit/clear row when simplifying the
  helper. Label its mouse/touch action “Ruler icon”, as explicitly requested.
