# Project Listing Page

This page describes the authenticated project listing and its supporting view
and controller.

---

## Overview

The project listing page (`frontend_private/templates/pages/projects.html`)
displays all projects the authenticated user has access to (excluding
`WEB_VIEWER`-only permissions). Projects are grouped by country with collapsible
sections, color indicators, and quick-action links.

---

## Data Flow

```
ProjectListingView (frontend_private/views/project.py)
  │
  ├─ request.user.permissions
  │   └─ Filter out WEB_VIEWER-only permissions
  │
  ├─ Project.objects
  │     .with_collaborator_count()
  │     .with_active_mutex()
  │     .filter(id__in=[...])
  │
  ├─ Build projects_data: list[ProjectInfoData]
  │   Each entry contains:
  │     - project: Project model instance
  │     - level_label: user's permission level label
  │     - active_mutex: ProjectMutex | None
  │
  └─ Group into projects_by_country: dict[str, list[ProjectInfoData]]
      ├─ Key: country name (str) or "Unknown"
      ├─ Sorted alphabetically by country name
      └─ Projects within each group sorted by name (case-insensitive)
```

### Template Context

| Variable              | Type                               | Description                         |
| --------------------- | ---------------------------------- | ----------------------------------- |
| `projects_data`       | `list[ProjectInfoData]`            | Flat list of all projects           |
| `projects_by_country` | `dict[str, list[ProjectInfoData]]` | Projects grouped by country, sorted |

---

## Permission Labels

Permission badges and selectors display `READ_AND_WRITE` as "Read & Write".
Django templates use the shared `normalize` filter, while JavaScript-rendered
GPS track and GIS overlay lists use
`frontend_common/presentation/permissions.ts`. Stored permission identifiers,
form option values, API payloads, and authorization rules are unchanged.

## Project Navigation

Project names in desktop rows and mobile cards link to
`private:project_details`, the same destination as the Open button. Names retain
their normal text styling until the name itself is hovered or keyboard-focused,
when a white underline reveals the link.

Desktop rows and mobile cards use a sky-blue "Open" button with a right-arrow
icon linking to `private:project_details`. Its visible background and minimum
height of 40px make the action easy to identify and click. Background and hover
colors match Unlock All (`sky-500` and `sky-600`), with a visible keyboard focus
outline. Each button includes an "Open project" tooltip and a project-specific
accessible label.

The private map viewer also supports `private:map_viewer?project=<project_id>`
deep links.

The private map viewer handles the project parameter after survey data loads. It
reveals the project through `ProjectPanel.revealProject`, including its country
gate, waits for display updates, and fits the project's survey bounds without a
camera animation. Other project visibility choices remain intact. An unavailable
project or missing survey geometry produces a notification. The project
parameter takes priority over the existing coordinate shortcut.

## Unlock Controls

Open, Unlock, and Force Unlock share a fixed width of 6rem and the same height.
Their desktop column has a fixed width of 112px, including cell padding, and
remains visible at every desktop breakpoint. The Open column is fixed at 124px,
allowing 20px of right padding against the table border while retaining the 6rem
button. The Project Name column absorbs the remaining table width. The lock
column heading is visually hidden; page-header actions wrap on narrow screens.

When the signed-in user owns a project's active lock, the lock column shows a
soft red "Unlock" button in place of their email. Project administrators see
only a "Force Unlock" button for another user's lock. Other editors' emails
remain visible to users without that action. Mobile cards retain the same
owner/admin controls in their Current Editor row.

Controls share `snippets/project_unlock_button.html` and the existing release
endpoint. Normal Unlock releases the signed-in user's lock immediately. Force
Unlock opens a confirmation modal showing the current editor's email and
releases only after confirmation. Editor emails are inserted as text. The Force
Unlock modal dims and blurs the page, highlights the current editor in a large
high-contrast panel, and places a red unsaved-changes warning above the actions.
Both paths keep the existing success and error feedback. Force Unlock moves
keyboard focus to Cancel, keeps Tab navigation inside the modal, and returns
focus to the triggering button on Cancel or Escape. Selecting the editor email
does not dismiss the modal.

## Country Grouping

The template iterates over `projects_by_country` and renders a collapsible
section per country. Both desktop (table rows) and mobile (cards) views are
grouped by country. Each section header includes:

- **Flag emoji** via the `country_flag` template filter (ISO alpha-2 to regional
  indicator emoji).
- **Country name** and project count.
- **Chevron icon** with CSS rotation indicating collapse state.

### Collapse persistence

Collapse state is stored in `localStorage` under
`DEFAULTS.STORAGE_KEYS.PROJECTS_COUNTRY_COLLAPSED`
(`speleo_projects_collapsed_countries`). The `projects` route controller reads
and writes a JSON array of collapsed ISO country codes (e.g. `["FR", "US"]`).

This is a separate key from the map viewer's
`DEFAULTS.STORAGE_KEYS.COUNTRY_COLLAPSED` (`speleo_country_collapsed`), which
controls the project panel inside the map viewer.

---

## Color Squares

Each project row displays a small colored square matching the project's `color`
field. The color is rendered server-side from `project.color` on the model. This
provides visual consistency with the map viewer, where the same color is used
for survey lines.

---

## Template Tags

| Tag/Filter                        | Source              | Usage                                    |
| --------------------------------- | ------------------- | ---------------------------------------- |
| `{% get_project_color_palette %}` | `project_colors.py` | Color picker presets on detail/new pages |
| `{{ code\|country_flag }}`        | `project_colors.py` | Emoji flag from ISO alpha-2 code         |

Both are registered in `speleodb/surveys/templatetags/project_colors.py`.

---

## Last Edit Display

Last Edit shows the month, day, and year without a time in both desktop rows and
mobile cards. The timestamp remains intact in the `time` element; the shared
browser date formatter uses date-only display in the user's local timezone.
Editing Since retains its existing timestamp display.

## Layout Decisions

### Fixed column widths (`table-fixed`)

The desktop table uses `table-fixed` with fixed pixel widths for the two action
columns, percentage widths for data columns, and an auto-sized name column. This
prevents column widths from shifting when country groups are expanded or
collapsed. With `table-auto`, hidden rows caused the browser to recalculate
column widths based only on visible content, creating a jarring layout shift.

Column width allocation (Project Name takes the remainder):

| Column          | Width | Rationale                 |
| --------------- | ----- | ------------------------- |
| Project Name    | auto  | Remaining width           |
| Software        | 9%    | Short badge               |
| Collaborators   | 8%    | Single number             |
| Revisions       | 7%    | Single number             |
| Permission      | 10%   | Badge text varies         |
| GPS Coordinates | 10%   | "Google Maps" link        |
| Last Edit       | 9%    | Browser-local date        |
| Current Editor  | 112px | Unlock button and padding |
| Editing Since   | 9%    | Browser-local timestamp   |
| Actions         | 124px | Open button and padding   |

### Page-level scroll (no container scrollbar)

The table wrapper has **no** `overflow-auto` or `max-h-*` constraint. The table
grows naturally and the page scrolls via the content column
(`base_private.html`: `overflow-y-auto`). This avoids a secondary scrollbar that
appears/disappears based on the number of projects.

### Sticky table header

The `<thead>` uses `sticky top-16 z-10`. `top-16` (4rem) matches the site header
height (`h-16`), so the table header sticks directly below the site header
(which is `sticky top-0 z-30`). The lower `z-10` keeps the table header below
the site header in stacking order.

### Collapse restoration

`frontend_common/app.ts` restores collapsed groups from local storage before
initializing route controllers. The template declares an inert `projects`
controller context; it contains no executable inline restoration script.
Unavailable or malformed local storage leaves the groups expanded.

---

## Key Files

| File                                              | Role                                                   |
| ------------------------------------------------- | ------------------------------------------------------ |
| `frontend_private/views/project.py`               | `ProjectListingView` builds context                    |
| `frontend_private/templates/pages/projects.html`  | Template with country grouping                         |
| `speleodb/surveys/templatetags/project_colors.py` | `country_flag` filter, `get_project_color_palette` tag |
| `speleodb/surveys/models/project.py`              | `Project.color` field                                  |
| `speleodb/common/enums.py`                        | `ColorPalette` (canonical 20-color palette)            |

## Software badges

Software choices and labels come from `ProjectType`. The project-type template
tags own badge colors for both desktop rows and mobile cards. Badge labels use
dark gray (`#373737`) for contrast with the light palette. The dashboard chart
references the same canonical mapping. See
[project capabilities](project-formats.md) for software, file-format, and
map-conversion boundaries.
