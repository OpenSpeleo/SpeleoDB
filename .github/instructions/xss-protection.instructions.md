---
applyTo: "**/*.js"
---

# XSS Protection — innerHTML Escaping

Any `.innerHTML` assignment that interpolates user-supplied data MUST escape
that data. Flag violations as **security** issues.

## Required pattern

Use `Utils.safeHtml` tagged template for `.innerHTML` assignments:

```js
// GOOD — safeHtml auto-escapes all interpolations
el.innerHTML = Utils.safeHtml`<h3>${station.name}</h3>`;

// GOOD — raw() opts out for trusted HTML fragments
el.innerHTML = Utils.safeHtml`<div>${Utils.raw(svgIcon)} ${station.name}</div>`;

// GOOD — explicit escapeHtml() in a bare template (acceptable in loops/concatenation)
html += `<h5>${Utils.escapeHtml(station.name)}</h5>`;
```

## What to flag

```js
// BAD — bare template literal with user data, no escaping
el.innerHTML = `<h3>${station.name}</h3>`;

// BAD — user data in attribute without escaping
el.innerHTML = `<span style="color: ${tag.color}">${tag.name}</span>`;

// BAD — concatenation without escaping user values
html += `<td>${value}</td>`;  // value could be user-supplied
```

## What NOT to flag

- `.innerHTML = ''` or `.innerHTML = 'static string'` (no interpolation)
- `.textContent = userInput` (textContent is safe by design)
- Interpolations of numeric computed values like `count`, `index + 1`,
  `latitude.toFixed(7)` — these cannot contain HTML
- `Utils.raw()` wrapping trusted HTML (SVG icons, conditional blocks)
- Templates inside test files (`*.test.js`)

## User-supplied data fields to watch for

station.name, station.description, tag.name, tag.color, landmark.name,
landmark.description, track.name, log.title, log.notes, log.created_by,
resource.title, resource.description, resource.created_by, experiment.name,
experiment.description, field.name, error.message, file.name, displayName,
projectName, networkName, noteData.title, noteData.author,
noteData.description, item.label, item.subtitle, message
