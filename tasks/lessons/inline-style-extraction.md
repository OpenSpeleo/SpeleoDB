# Preserve declarations and cascade when extracting inline styles

Removing a style attribute can leave a tag with no attributes. Add its
replacement class even when there is no remaining space in the opening tag; do
not implement attribute insertion by replacing the first space. Compare every
original inline style with its replacement, including style-only spans and
layout wrappers.

Tailwind utilities are layered and may lose to existing unlayered component or
mobile CSS. Match the original computed behavior with an owning selector where
needed, and preserve the ability of runtime inline styles to resize maps or show
modals. Avoid `!important` on values the runtime updates.
