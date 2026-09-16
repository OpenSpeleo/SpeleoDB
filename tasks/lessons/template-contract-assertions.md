# Test template contracts independently of HTML serialization

When styles move to utilities, update template tests alongside the templates.
Check the relevant element's classes and dimensions instead of searching the
whole document for obsolete inline CSS. Match chart containers directly to their
canvases rather than inspecting an arbitrary preceding character window.

Void tags may render with or without a trailing slash. Theme tests should
inspect metadata attributes and document ordering rather than require an exact
tag string. Preserve checks for dark scheme values, Dark Reader lock placement,
private-only dark classes, and stylesheet cascade order.
