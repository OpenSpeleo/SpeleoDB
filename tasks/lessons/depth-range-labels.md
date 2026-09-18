# Name the depth range by what it shows

The user prefers **Full range** over **Automatic** for an uncapped depth scale.
Use that label in the disclosure summary and input placeholder. Name the action
**Reset to Full Depth Range**. Keep the help concise: **Colors and depth
readings stop at this limit.** Do not add the removed explanation about leaving
the input blank. Document how project visibility affects the range in the
feature docs. Keep documentation and UI test expectations aligned.

Keep the collapsed depth-limit row visually quiet, even with an active cap.
Apply the colored border, background, and value badge only when the disclosure
is open.

Explain the purpose visibly in the expanded setting: one unusually deep cave can
compress the shared color scale and hide color differences in shallower
passages. Lead with a short heading and readable explanation above the numeric
control.

Make the depth reset a full-width secondary button with a minimum 44px target,
not a small text link.
