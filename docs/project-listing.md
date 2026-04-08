# Project Listing Page

> Agent-focused documentation for the `projects.html` template and its
> supporting view logic.

---

## Overview

The project listing page (`frontend_private/templates/pages/projects.html`)
displays all projects the authenticated user has access to (excluding
`WEB_VIEWER`-only permissions). Projects are grouped by country with
collapsible sections, color indicators, and quick-action links.

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

| Variable | Type | Description |
|---|---|---|
| `projects_data` | `list[ProjectInfoData]` | Flat list of all projects |
| `projects_by_country` | `dict[str, list[ProjectInfoData]]` | Projects grouped by country, sorted |

---

## Country Grouping

The template iterates over `projects_by_country` and renders a collapsible
section per country. Both desktop (table rows) and mobile (cards) views
are grouped by country. Each section header includes:

- **Flag emoji** via the `country_flag` template filter (ISO alpha-2 to
  regional indicator emoji).
- **Country name** and project count.
- **Chevron icon** with CSS rotation indicating collapse state.

### Collapse persistence

Collapse state is stored in `localStorage` under
`DEFAULTS.STORAGE_KEYS.PROJECTS_COUNTRY_COLLAPSED`
(`speleo_projects_collapsed_countries`). The inline `<script>` reads and
writes a JSON array of collapsed ISO country codes (e.g. `["FR", "US"]`).

This is a separate key from the map viewer's
`DEFAULTS.STORAGE_KEYS.COUNTRY_COLLAPSED` (`speleo_country_collapsed`),
which controls the project panel inside the map viewer.

---

## Color Squares

Each project row displays a small colored square matching the project's
`color` field. The color is rendered server-side from `project.color` on
the model. This provides visual consistency with the map viewer, where
the same color is used for survey lines.

---

## Template Tags

| Tag/Filter | Source | Usage |
|---|---|---|
| `{% get_project_color_palette %}` | `project_colors.py` | Color picker presets on detail/new pages |
| `{{ code\|country_flag }}` | `project_colors.py` | Emoji flag from ISO alpha-2 code |

Both are registered in `speleodb/surveys/templatetags/project_colors.py`.

---

## Key Files

| File | Role |
|---|---|
| `frontend_private/views/project.py` | `ProjectListingView` builds context |
| `frontend_private/templates/pages/projects.html` | Template with country grouping |
| `speleodb/surveys/templatetags/project_colors.py` | `country_flag` filter, `get_project_color_palette` tag |
| `speleodb/surveys/models/project.py` | `Project.color` field |
| `speleodb/common/enums.py` | `ColorPalette` (canonical 20-color palette) |
