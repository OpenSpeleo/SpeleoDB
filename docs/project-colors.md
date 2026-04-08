# Project & GPS Track Colors

> Agent-focused documentation for the color system spanning Django
> models, API serializers, Django templates, and the JS map viewer.

---

## Design Intent

Every project and GPS track has a persistent hex color used for map
rendering (survey lines, track lines, color dots in panels) and UI
indicators (project listing page, detail pages, GPS track list). Colors
are stored on the model so they survive across sessions and are
consistent for all users viewing the same data.

---

## ColorPalette (Python)

**File:** `speleodb/common/enums.py`

`ColorPalette` is the single source of truth for the 20-color palette:

- `COLORS` — tuple of 20 perceptually distinct hex strings.
- `random_color()` — classmethod returning a random entry (used as
  the model field default).
- `is_valid_hex(value)` — static method validating `#[0-9a-fA-F]{6}`.

Both `Project.color` and `GPSTrack.color` reference `ColorPalette`.

---

## Model Fields

### `Project.color`

**File:** `speleodb/surveys/models/project.py`

```python
color = models.CharField(
    max_length=7,
    default=ColorPalette.random_color,
    help_text="Hex color code for map rendering (e.g. #e41a1c)",
)
```

### `GPSTrack.color`

**File:** `speleodb/gis/models/gps_track.py`

```python
color = models.CharField(
    max_length=7,
    default=ColorPalette.random_color,
    help_text="Hex color code for map rendering (e.g. #e41a1c)",
)
```

Both default to `ColorPalette.random_color`, producing a random palette
entry at creation time. Format: 7-character hex string (`#rrggbb`).

### Migrations

- `speleodb/surveys/migrations/0027_project_color.py` — adds
  `Project.color` with `RunPython` to assign random colors to existing
  rows.
- `speleodb/gis/migrations/0035_gpstrack_color.py` — adds
  `GPSTrack.color` with the same pattern.

---

## Serializer Validation

**Files:** `speleodb/api/v1/serializers/project.py`,
`speleodb/api/v1/serializers/gps_track.py`

Both serializers implement `validate_color()`:

- Validates format via `ColorPalette.is_valid_hex()`.
- Normalizes to lowercase on write.

`GPSTrackSerializer` has a custom `update()` method that passes
`update_fields` to `save()`, so metadata-only changes (like color) skip
S3 file re-hashing. `GPSTrack.save()` skips file hashing when
`update_fields` is provided and doesn't include `file`.

---

## Template Tag & Filter

**File:** `speleodb/surveys/templatetags/project_colors.py`

### `{% get_project_color_palette %}`

Simple tag that returns `ColorPalette.COLORS`. Used by the color picker
UI on `details.html`, `new.html`, and the GPS track edit modal to render
preset swatches.

### `{{ code|country_flag }}`

Filter that converts an ISO alpha-2 country code to its emoji flag.
Co-located in the same templatetags file. See
`docs/project-listing.md` for usage context.

---

## Color Picker UI

**Pages:** `details.html`, `new.html` (projects), GPS track edit modal

The color picker renders:

1. **Preset swatches** from `{% get_project_color_palette %}` — clicking
   a swatch sets the hex input and preview.
2. **Native color picker** triggered via an SVG icon
   (`media/color-picker.svg`) — provides full color spectrum access.
3. **Editable hex input** with a `#` prefix — accepts manual hex entry.

### Read-only projects

For users without write access:

- The color picker container has `opacity: 0.5` and
  `pointer-events: none`.
- Preset swatches are hidden.
- The save button is grayed with `cursor: not-allowed`.

### GPS track color dots

The GPS track list on `gps_tracks.html` shows a color dot next to each
track name, rendered server-side from `track.color`.

---

## Map Viewer: Color Resolution

**File:** `frontend_private/static/private/js/map_viewer/map/colors.js`

There is **no palette array in JS**. All colors are model-driven.

### `Colors.getProjectColor(projectId)`

1. Check `projectColorMap` cache — return if hit.
2. Look up `Config.getProjectById(projectId).color` — cache and return.
3. If project not yet in Config, return `FALLBACK_COLOR` (`#94a3b8`)
   **without caching** — the next call retries, resolving timing issues
   during initialization.

### `Colors.getGPSTrackColor(trackId)`

Same pattern via `Config.getGPSTrackById(trackId).color`, falling back
to `FALLBACK_COLOR` without caching.

### Reset functions (testing)

- `Colors.resetColorMap()` — clears project color cache.
- `Colors.resetGPSTrackColorMap()` — clears GPS track color cache.

---

## Public Viewer Behavior

`Config.setPublicProjects()` maps the `color` field from the public GIS
API response (`project_color`). The public GIS serializer
(`PublicGISProjectViewSerializer`) includes `color`. As a result,
`Colors.getProjectColor()` works identically in both viewers — reading
the model-stored color from Config.

The public viewer does not have GPS tracks.

---

## Key Files

| File | Role |
|---|---|
| `speleodb/common/enums.py` | `ColorPalette` — canonical palette, validation, random assignment |
| `speleodb/surveys/models/project.py` | `Project.color` field |
| `speleodb/gis/models/gps_track.py` | `GPSTrack.color` field |
| `speleodb/api/v1/serializers/project.py` | `ProjectSerializer.validate_color()` |
| `speleodb/api/v1/serializers/gps_track.py` | `GPSTrackSerializer.validate_color()`, custom `update()` |
| `speleodb/api/v1/serializers/gis_view.py` | `PublicGISProjectViewSerializer` with `color` field |
| `speleodb/surveys/templatetags/project_colors.py` | `get_project_color_palette` tag, `country_flag` filter |
| `frontend_private/static/private/js/map_viewer/map/colors.js` | `getProjectColor()`, `getGPSTrackColor()`, `FALLBACK_COLOR` |
| `frontend_private/static/private/js/map_viewer/config.js` | `loadProjects()`, `loadGPSTracks()`, `setPublicProjects()`, `getGPSTrackById()` |
| `frontend_private/templates/pages/project/details.html` | Color picker UI (projects) |
| `frontend_private/templates/pages/project/new.html` | Color picker UI (new project) |
| `frontend_private/templates/pages/gps_tracks.html` | GPS track color dots and edit modal |
