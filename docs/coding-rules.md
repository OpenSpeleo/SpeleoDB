# Coding Rules

Hard rules for all code in this repository. Violations must be fixed
before merging.

---

## JavaScript / Frontend

### All constants belong in `config.js`

**Every tuneable constant** in the map viewer must be defined in the
`DEFAULTS` object exported from `config.js`. No magic numbers, thresholds,
durations, zoom levels, colors, sizes, or configuration values anywhere else.

```javascript
// BAD — hardcoded constant in a random module
const DRAG_THRESHOLD = 10;
const LIMITED_MAX_ZOOM = 13;
map.fitBounds(allBounds, { padding: 50, maxZoom: 16 });
setTimeout(() => overlay.remove(), 500);

// GOOD — import from config.js
import { DEFAULTS } from '../config.js';
// ...then use DEFAULTS.DRAG.THRESHOLD_PX, DEFAULTS.MAP.LIMITED_MAX_ZOOM, etc.
```

The `DEFAULTS` object is organized by category:

| Category | Examples |
|---|---|
| `DEFAULTS.MAP` | style URL, center, zoom levels, fit bounds padding |
| `DEFAULTS.ZOOM_LEVELS` | min zoom per layer type |
| `DEFAULTS.SNAP` | magnetic snap radius |
| `DEFAULTS.DRAG` | drag threshold, query padding |
| `DEFAULTS.UI` | mobile breakpoint, notification duration, truncation lengths |
| `DEFAULTS.UPLOAD` | max file size |
| `DEFAULTS.COLORS` | default station color |
| `DEFAULTS.STORAGE_KEYS` | localStorage key names |

When adding a new feature that needs a tuneable value, add it to `DEFAULTS`
first, then import it where needed.

---

## Python / Backend

### Import & Module-Level Code

- **Never place executable statements (assignments, function calls) between
  import groups.** `logger = logging.getLogger(__name__)` and similar
  module-level assignments go **after all imports** (including
  `if TYPE_CHECKING` blocks), never in the middle. Violating this causes
  ruff E402 for every import that follows.
- Import order enforced by ruff/isort: `__future__` -> stdlib -> third-party
  -> local -> `TYPE_CHECKING`. No code between these groups.

### Django ORM

- **Never materialize a queryset to grab one element.**
  Use `.first()` / `.last()` / `.get()`, not `list(qs)[0]`.
- **Never filter in Python when the ORM can do it.**
  Use `.filter(field=value).first()`, not
  `next(x for x in qs.all() if x.field == value)`.
- **Use `.count()` not `len(list(qs))`, `.exists()` not `bool(list(qs))`.**
- Always add `select_related()` / `prefetch_related()` when accessing FK
  fields in serializers or loops to avoid N+1 queries.
