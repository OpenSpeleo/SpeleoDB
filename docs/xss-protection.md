# XSS Protection

## Why

Users can enter names like `<WIP> Sensor Type` or `A & B`. These must
display correctly -- not get stripped, not execute as HTML. The fix is
**render-side escaping**: the backend stores raw text, the frontend escapes
before inserting into the DOM.

## Core API (ES module files)

### `Utils.escapeHtml(text)`

Escapes `<`, `>`, `&`, `"`, `'` so the value is safe in both HTML text
content **and** HTML attribute positions. Returns empty string for
`null`/`undefined`.

```js
import { Utils } from '../utils.js';

container.innerHTML = `<h3>${Utils.escapeHtml(station.name)}</h3>`;
```

### `Utils.safeHtml` tagged template

Auto-escapes all interpolations. Use for multi-line innerHTML assignments:

```js
container.innerHTML = Utils.safeHtml`
    <h3>${station.name}</h3>
    <p>${station.description}</p>
    ${Utils.raw(trustedIconMarkup)}
`;
```

### `Utils.raw(htmlString)`

Marks a value as pre-trusted (static HTML, SVG icons, conditional blocks).
**Never** wrap strings that contain unescaped user data.

### `Utils.isValidCssColor(color)` / `Utils.safeCssColor(color, fallback)`

Validates that a color string is a valid hex color (`#RGB` or `#RRGGBB`).
Use before interpolating user-supplied colors into `style` attributes to
prevent CSS injection. Returns the fallback (default `#94a3b8`) for invalid
values.

```js
const safeColor = Utils.safeCssColor(tag.color);
el.innerHTML = `<span style="background-color: ${safeColor}">...</span>`;

// Inside Utils.safeHtml, wrap in Utils.raw() since safeCssColor already validates
el.innerHTML = Utils.safeHtml`<span style="background-color: ${Utils.raw(Utils.safeCssColor(tag.color))}">...</span>`;
```

### `Utils.sanitizeUrl(url)`

Validates that a URL is safe for use in `href` and `src` attributes.
Allows `http:`, `https:`, and relative URLs. Rejects `javascript:`,
`data:`, `vbscript:`, and other dangerous schemes. Returns empty string
for invalid URLs.

```js
// Always sanitize API-supplied URLs before inserting into href/src
`<a href="${Utils.sanitizeUrl(resource.file)}">View</a>`;
`<img src="${Utils.sanitizeUrl(resource.miniature)}">`;
```

## Shared global helpers (`xss-helpers.js`)

`frontend_private/static/private/js/xss-helpers.js` defines `escapeHtml`,
`safeCssColor`, `isValidCssColor`, and `sanitizeUrl` as global functions.
It is loaded in `base_private.html` before any page-specific scripts, so
every inline `<script>` block can call these directly without redefining
them.

```js
// In any inline <script> block or non-module .js file:
tableBody.html(`<td>${escapeHtml(tag.name)}</td>`);
const safe = safeCssColor(tag.color);
```

**Do not** define local copies of `escapeHtml` in templates or standalone
scripts. Use the global.

For ES module files (map viewer), import from `utils.js` instead:

```js
import { Utils } from '../utils.js';
html += `<td>${Utils.escapeHtml(value)}</td>`;
```

jQuery `.text()` is also safe for plain text (error messages, labels):

```js
$('#error').text(errorMsg);   // GOOD
$('#error').html(errorMsg);   // BAD
```

## What to escape

Any field a user or API can control: names, descriptions, notes, titles,
tag names, sensor names, experiment field names, cell values, GPS track
names, line names, error messages, file names, author names, status labels,
resource URLs (`resource.file`, `resource.miniature`, `log.attachment`),
and resource text content (`resource.text_content`).

## What NOT to escape

Static HTML, SVG icons, CSS classes, numeric coordinates, boolean
attributes, values already inside `Utils.raw()`.

## Attribute contexts

`escapeHtml` escapes both `"` and `'`, making it safe for attribute values:

```js
// Safe -- quotes in station.name won't break out of value=""
el.innerHTML = Utils.safeHtml`<input value="${station.name}">`;
```

## URL attributes

API-supplied URLs in `href` and `src` attributes must be validated with
`Utils.sanitizeUrl()` to block `javascript:` and other dangerous schemes:

```js
// BAD -- javascript: protocol executes on click
`<a href="${resource.file}">View</a>`;

// GOOD -- sanitizeUrl rejects non-http(s) URLs
`<a href="${Utils.sanitizeUrl(resource.file)}">View</a>`;
```

## HTML sinks to watch

All of these parse HTML and are XSS vectors if given unescaped user data:

- `element.innerHTML = ...`
- `element.insertAdjacentHTML('beforeend', ...)`
- `$(selector).html(...)`
- `Modal.base(title, content, footer)` -- callers must pre-escape
- `href="${url}"` / `src="${url}"` -- use `Utils.sanitizeUrl()`

Safe alternatives that never parse HTML:

- `element.textContent = ...`
- `$(selector).text(...)`

## Architecture: two canonical locations

1. **`xss-helpers.js`** -- global functions for inline `<script>` blocks
   and non-module JS files. Loaded once in `base_private.html`.
2. **`Utils` in `utils.js`** -- same functions wrapped in the ES module
   API for map viewer modules. Tested via `utils.test.js`.

Both implement the same escaping logic. When changing the algorithm,
update **both** files and run `npm run test:js`.

## `ajax_error_modal_management.js`

This shared snippet is included in 28+ Django templates. It calls
`escapeHtml()` (from `xss-helpers.js`) on all API error fields before
inserting into the error modal.

---

## Server-side sanitization (defense-in-depth)

The backend strips HTML tags from all user text fields before saving to
the database. This is defense-in-depth -- even if a frontend escaping
path is missed, the stored data cannot contain executable HTML.

### Pipeline

`speleodb/utils/sanitize.py` defines `sanitize_text()` which runs:

1. **`nh3.clean(value, tags=set())`** -- strips ALL HTML tags, keeps
   text content only. `<script>alert(1)</script>` becomes `alert(1)`.
2. Unicode NFD decomposition + combining mark removal (anti-zalgo).
3. NFC recomposition.
4. Control/format character removal.
5. Whitespace normalization.

### Integration

`SanitizedFieldsMixin` (in `speleodb/utils/serializer_mixins.py`) runs
`sanitize_text()` on every field listed in a serializer's
`sanitized_fields` during `to_internal_value()`. 21 serializer classes
across the codebase use this mixin, covering ~50 text fields.

### What this means for users

Angle brackets in text fields are stripped: `<WIP> Station` becomes
`WIP Station`. This is an explicit trade-off for security.

### Tag color validation

`StationTagSerializer.validate_color` rejects any value that is not a
6-digit hex code (`#RRGGBB`). This prevents CSS injection via
`style="background-color: ${tag.color}"` on the frontend.
