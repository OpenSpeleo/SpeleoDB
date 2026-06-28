# Verify split-stylesheet components on the real rendered route

A synthetic browser fixture is not a live parity test merely because it
concatenates the generated and handwritten stylesheets. Raw Django template
source does not execute inheritance, includes, conditional branches, URL/static
tags, or page-level style blocks. Reading ignored CSS directly from disk also
bypasses the asset that the running application actually serves; an active
Tailwind watcher may retain a deleted candidate until a clean build.

For components whose appearance spans generated utilities, handwritten rules,
and inline page styles, navigate the real rendered route and verify the exact
stylesheet/style-block order plus the served asset hashes. Build from a clean
process, render the real state and permissions, and inspect cascade winners in
addition to pixels. A focused fixture may help reduce a defect, but it cannot
replace the live-route proof.

Prefer expressing a one-off visual contract with source-scanned utilities, or
move a reusable abstraction into the processed component layer. Do not preserve
a legacy selector merely by relocating the same declaration.
