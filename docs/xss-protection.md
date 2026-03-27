# XSS Protection

## Why

Users can enter names like `<WIP> Sensor Type` or `A & B`. These must
display correctly — not get stripped, not execute as HTML. The fix is
**render-side escaping**: the backend stores raw text, the frontend escapes
before inserting into the DOM.

## How

### ES module files (map viewer)

Use `Utils.escapeHtml()` on any user data going into `innerHTML` or `.html()`:

```js
import { Utils } from '../utils.js';

container.innerHTML = `<h3>${Utils.escapeHtml(station.name)}</h3>`;
```

Or use the `Utils.safeHtml` tagged template — it auto-escapes all interpolations:

```js
container.innerHTML = Utils.safeHtml`
    <h3>${station.name}</h3>
    <p>${station.description}</p>
    ${Utils.raw(trustedIconMarkup)}
`;
```

`Utils.raw()` marks a value as pre-trusted (static HTML, SVG icons, conditional blocks).

### Django template inline scripts

Inline `<script>` blocks can't import ES modules. Define `escapeHtml()` locally:

```js
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

tableBody.html(`<td>${escapeHtml(tag.name)}</td>`);
```

## What to escape

Any field a user can edit: names, descriptions, notes, titles, tag names,
sensor names, experiment field names, cell values, GPS track names.

## What NOT to escape

Static HTML, SVG icons, CSS classes, numeric coordinates, boolean attributes.
