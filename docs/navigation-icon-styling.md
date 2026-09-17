# Navigation icon styling

## Shared navigation sections

`base_private.html` owns one responsive `#sidebar`: it is a mobile drawer and
becomes the desktop sidebar at the `lg` breakpoint. Keep navigation items in
that shared markup so labels, ordering, links, and active states stay aligned.
The sidebar is 290px wide on desktop and mobile, capped at the viewport width.
This leaves room for indented GIS labels. The closed mobile drawer translates by
its full width so a wider drawer does not leave a visible strip. The sidebar
header uses symmetric `my-3` spacing; its mobile spacing/logo rules target that
same header class combination.

GIS Survey Map sits immediately below Survey Tools in the first section. A
subtle sky-blue tint, thin border, and brighter compass icon distinguish the
link without adding a large button or animation; its active page retains indigo
selection styling.

The second section is a native `details` disclosure labelled **GIS Tooling**,
with the supplied map-pin/layers icon at the standard 24px sidebar size and a
12px label gap. The decorative icon inherits slate coloring and is hidden from
assistive technology; the separate chevron indicates disclosure state. The group
contains GIS Cylinder Fleets, GIS Experiments, GIS Geometries, GIS Landmark
Collections, GIS Layers, GIS Sensor Fleets, GIS Station Tags, GIS Surface
Monitoring, and GIS Views in alphabetical order. The nested list is indented
with a subtle left border. Child labels wrap rather than truncate so the extra
indentation does not hide long names on narrow screens. GIS Geometries and GIS
Layers omit the My prefix here; their listing headings remain unchanged. Move
entire template blocks so route-family highlighting and icons travel with their
links.

The disclosure starts collapsed on each page. The `private-navigation` Vite
controller opens it if a descendant link has `aria-current="page"`. Existing
server route highlighting emits that marker for every grouped listing, creation
page, and settings tab (including cylinder hydro/visual watchlists). This avoids
maintaining a second route registry. The native summary supplies keyboard
toggling and expanded-state accessibility; users can still collapse it on an
active page. No local storage, event listeners, API requests, or per-feature
scans are needed; initialization performs one bounded DOM lookup.

The private template regression suite checks rendered navigation and every
grouped route's current-page marker. Controller tests cover default collapse,
automatic expansion, and manual toggling. Browser checks cover pointer/keyboard
interaction in the desktop sidebar and mobile drawer.

## Outline icons

The main private sidebar's Give us Feedback paper-plane icon uses an explicit
`fill="none"`, preventing SVG's default black fill from obscuring its interior.
Stroke and active/inactive color classes belong on the SVG, as on neighboring
navigation icons. Preserve its existing size, stroke weight, geometry, spacing,
and slate/indigo selection colors.

This is template-owned presentation with no additional scripts or runtime work.
Validate template formatting/lint, the frontend suite, and a clean Vite build
inside the running application container when changing these styles.
