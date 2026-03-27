---
applyTo: "**/*.{js,html}"
---

# XSS Protection -- innerHTML Escaping

Any `.innerHTML` assignment, jQuery `.html()` call, or `insertAdjacentHTML`
that interpolates user-supplied data MUST escape that data. Flag violations
as **security** issues.

## Required pattern

Use `Utils.safeHtml` tagged template for `.innerHTML` assignments:

```js
// GOOD -- safeHtml auto-escapes all interpolations
el.innerHTML = Utils.safeHtml`<h3>${station.name}</h3>`;

// GOOD -- raw() opts out for trusted HTML fragments
el.innerHTML = Utils.safeHtml`<div>${Utils.raw(svgIcon)} ${station.name}</div>`;

// GOOD -- explicit escapeHtml() in a bare template (acceptable in loops/concatenation)
html += `<h5>${Utils.escapeHtml(station.name)}</h5>`;

// GOOD -- textContent is always safe
el.textContent = station.name;

// GOOD -- jQuery .text() is always safe
$('#error').text(errorMsg);
```

## What to flag

```js
// BAD -- bare template literal with user data, no escaping
el.innerHTML = `<h3>${station.name}</h3>`;

// BAD -- user data in attribute without escaping
el.innerHTML = `<span style="color: ${tag.color}">${tag.name}</span>`;

// BAD -- concatenation without escaping user values
html += `<td>${value}</td>`;  // value could be user-supplied

// BAD -- jQuery .html() with user/API data
$('#error').html(errorMsg);
$('#modal').html(`<p>${data.message}</p>`);

// BAD -- Utils.raw() wrapping a string with unescaped user data inside
el.innerHTML = Utils.safeHtml`${Utils.raw(`<span>${parentName}</span>`)}`;
```

## Additional sinks to flag

```js
// BAD -- API URL in href without sanitization
`<a href="${resource.file}">View</a>`;

// GOOD -- sanitizeUrl blocks javascript: and other dangerous schemes
`<a href="${Utils.sanitizeUrl(resource.file)}">View</a>`;

// BAD -- user-controlled color in style without validation
`<span style="background-color: ${tag.color}">`;

// GOOD -- safeCssColor validates hex format
`<span style="background-color: ${Utils.safeCssColor(tag.color)}">`;
```

## What NOT to flag

- `.innerHTML = ''` or `.innerHTML = 'static string'` (no interpolation)
- `.textContent = userInput` (textContent is safe by design)
- `$(selector).text(userInput)` (jQuery .text() is safe by design)
- Interpolations of numeric computed values like `count`, `index + 1`,
  `latitude.toFixed(7)` -- these cannot contain HTML
- `Utils.raw()` wrapping trusted HTML (SVG icons, conditional blocks)
- Templates inside test files (`*.test.js`)
- CSS color values validated with `Utils.isValidCssColor()` or
  `Utils.safeCssColor()`
- URL values validated with `Utils.sanitizeUrl()`

## User-supplied data fields to watch for

station.name, station.description, tag.name, tag.color, landmark.name,
landmark.description, track.name, log.title, log.notes, log.created_by,
log.attachment, resource.title, resource.description, resource.created_by,
resource.file, resource.miniature, resource.text_content, experiment.name,
experiment.description, field.name, error.message, file.name, displayName,
projectName, networkName, noteData.title, noteData.author,
noteData.description, item.label, item.subtitle, message, parentName,
snapResult.lineName, snapResult.pointType, sensorName, sensor_name,
sensor_fleet_name, install_user, uninstall_user, lineName, lead.createdBy,
lead.description, errorMsg, completenessValidation.errorMessage,
titleCaseText, data.responseJSON fields
