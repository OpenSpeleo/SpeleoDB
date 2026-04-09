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
| `DEFAULTS.UI` | mobile breakpoint, notification duration, truncation lengths, `COUNTRY_GROUP_TRANSITION_MS` |
| `DEFAULTS.UPLOAD` | max file size |
| `DEFAULTS.COLORS` | `DEFAULT_STATION`, `FALLBACK` (`#94a3b8` — used when model color is not yet loaded), `DEPTH_NONE`/`DEPTH_SHALLOW`/`DEPTH_MID`/`DEPTH_DEEP` (depth gradient) |
| `DEFAULTS.STORAGE_KEYS` | localStorage key names: `COUNTRY_COLLAPSED`, `COUNTRY_VISIBILITY`, `PROJECTS_COUNTRY_COLLAPSED`, plus project/network visibility keys |

When adding a new feature that needs a tuneable value, add it to `DEFAULTS`
first, then import it where needed.

### No unescaped user data in HTML sinks

**Every** `innerHTML` assignment, jQuery `.html()` call, or
`insertAdjacentHTML` that interpolates user- or API-supplied data **must**
escape that data first. This applies to ES module files **and** inline
`<script>` blocks in Django templates.

```javascript
// BAD — user data injected raw into HTML
el.innerHTML = `<h3>${station.name}</h3>`;
$('#error').html(errorMsg);

// GOOD — ES module: use Utils.safeHtml / Utils.escapeHtml
el.innerHTML = Utils.safeHtml`<h3>${station.name}</h3>`;
html += `<td>${Utils.escapeHtml(value)}</td>`;

// GOOD — inline template script: use local escapeHtml or .text()
$('#error').text(errorMsg);
tableBody.html(`<td>${escapeHtml(tag.name)}</td>`);

// GOOD — safe alternative: textContent (never parses HTML)
el.textContent = station.name;
```

**Attribute contexts** (e.g. `value="..."`, `data-*="..."`) require quote
escaping. `Utils.escapeHtml` escapes `"` and `'` in addition to `<`, `>`,
`&`.

**`Utils.raw()`** marks content as pre-trusted and bypasses escaping.
Never wrap strings that contain unescaped user data in `Utils.raw()`.

**CSS color values** in `style` attributes must be validated with
`Utils.isValidCssColor()` or `Utils.safeCssColor()` before interpolation.

**URL attributes** (`href`, `src`) with API-supplied values must be
validated with `Utils.sanitizeUrl()` to block `javascript:` and other
dangerous schemes.

**Inline event handlers** (`onclick="..."`) should be avoided. Use
`data-*` attributes with `addEventListener` instead. If inline handlers
are unavoidable, any interpolated values must be escaped.

**Do not** define local `escapeHtml` / `safeCssColor` functions in
templates or standalone scripts. Use the global functions from
`xss-helpers.js` (loaded in `base_private.html`). ES module files
should use `Utils.escapeHtml` from `utils.js`.

See `docs/xss-protection.md` for the full rationale and patterns.

---

## Python / Backend

### Import & Module-Level Code

- **All imports must be at the top of the file.** Never use inline/local
  imports inside functions, methods, or `setUp`. This violates ruff PLC0415.
  If you need a symbol, import it at the top with all other imports.

```python
# BAD — inline import inside a method
def test_something(self) -> None:
    from speleodb.common.enums import ProjectType  # PLC0415!
    ...

# GOOD — import at the top of the file
from speleodb.common.enums import ProjectType

def test_something(self) -> None:
    ...
```

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
