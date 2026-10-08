# XSS Protection

## Rendering boundary

User and API values must remain text when displayed. Escape at the function that
writes HTML, rather than relying on callers to pre-escape. Backend sanitization
is defense in depth on designated fields; it is not a substitute for output
encoding and does not cover every data source.

Prefer DOM `textContent` or jQuery `.text()` for plain messages, names, and
labels. `innerHTML`, `insertAdjacentHTML`, and jQuery `.html()` all parse markup
and need an explicit trust boundary.

## Shared ES module APIs

`frontend_private/static/private/ts/xss-helpers.ts` exports `escapeHtml`,
`isValidCssColor`, `safeCssColor`, and `sanitizeUrl` for form/route modules. Map
viewer modules use the equivalent `Utils` API in `map_viewer/utils.ts`, which
also provides `safeHtml` and `raw`. Both facades delegate escaping, URL
sanitization and color validation to the small modules under
`frontend_common/security/`. Keep policy in the facade: form `safeCssColor`
replaces a falsey fallback with its default, while the map method preserves an
explicit empty fallback and calls its receiver's current validator.
`Utils.safeHtml` likewise calls the current `Utils.escapeHtml`; raw tokens
retain their module-owned identity. This preserves mutable facade behavior while
keeping security primitives independent of map state and transport. Neither
helper is a template global. Vite controllers import dependencies, and Django
templates provide inert context rather than executable inline scripts.

```js
import { escapeHtml } from "../xss-helpers.ts";

tableBody.html(`<td>${escapeHtml(tag.name)}</td>`);
$("#error").text(errorMessage);
```

`escapeHtml` converts values with `String()`, returns an empty string for
null/undefined, and escapes `<`, `>`, `&`, double quotes, and apostrophes. Quote
escaping is required for quoted attribute values; using a DOM element solely to
escape text does not escape attribute quotes automatically.

```js
import { Utils } from "../utils.ts";

container.innerHTML = Utils.safeHtml`
    <h3>${station.name}</h3>
    <input value="${station.name}">
    <p>${station.description}</p>
    ${Utils.raw(trustedIconMarkup)}
`;
```

`Utils.safeHtml` escapes direct interpolations. `Utils.raw()` only marks a value
as trusted; it does not sanitize anything. Use it for static markup or a helper
whose HTML is already safely constructed. An unsafe nested template literal or
helper result wrapped in `raw()` bypasses protection. Prefer `safeHtml` within
the helper itself so the escaping boundary stays visible.

## Attribute-specific validation

URL validation and HTML escaping solve different problems. `sanitizeUrl` accepts
HTTP(S) and relative URLs and rejects dangerous schemes such as `javascript:`.
Its returned string still needs attribute escaping if inserted into HTML. Prefer
safe interpolation or assign a validated value through the DOM:

```js
container.innerHTML = Utils.safeHtml`
    <a href="${Utils.sanitizeUrl(resource.file)}">View</a>
    <img src="${Utils.sanitizeUrl(resource.miniature)}" alt="">
`;
link.href = Utils.sanitizeUrl(log.attachment);
```

Colors inserted into styles must pass `isValidCssColor` or `safeCssColor`. They
accept only `#RGB`/`#RRGGBB`; the map utility defaults to the configured
fallback `#94a3b8`. Validation prevents CSS declarations or URLs from being
smuggled into a color value. Keep the interpolation escaped too:

```js
container.innerHTML = Utils.safeHtml`
    <span style="background-color: ${Utils.safeCssColor(tag.color)}">Tag</span>
`;
```

Do not interpolate user values into application event handlers. Use delegated
`data-*` actions or listeners in modules. Static SVG/HTML may be trusted, but a
value's presence inside `raw()` is never evidence that it is safe. Numbers and
booleans must be validated as such before treating them as non-string data.

## Sink ownership and verification

Names, notes, descriptions, tags, field names, filenames, author/status labels,
errors, and resource text are all user/API-controlled. The function assembling
the final markup owns their escaping, including helper return values accepted by
modal builders. `forms/ajax_errors.ts` imports the shared escape helper and uses
`.text()` where markup is unnecessary; templates no longer include the old
executable error snippet.

The feedback controller joins API error messages in response order, then passes
the result through `escapeHtml` before calling `FormModals.showError`. The modal
facade deliberately accepts trusted application HTML; escaping belongs to the
controller that knows these messages came from an API. Valid text, quotes and
entity-like strings remain literal, and tags or event attributes cannot create
elements. Tests exercise the real modal renderer, preserve submission/reset and
fallback behavior, and check that malicious responses remain inert.

Use real escaping helpers in rendering tests. A stub that escapes fewer
characters can conceal a regression. Exercise text and attribute breakouts,
malicious URL schemes, CSS injection, null/non-string inputs, and nested helper
results. Run frontend tests inside the already-running application container.
Encoding performs local string work and adds no network or database access.

## Server-side sanitization

`speleodb/utils/serializer_mixins.py::SanitizedFieldsMixin` transforms only
incoming string fields named in a serializer's `sanitized_fields`. It does not
sanitize outgoing representations, arbitrary stored rows, or every application
text field. After field-level validation, it invokes `sanitize_text` during
`to_internal_value`; invariants that can be invalidated by sanitization need
validation after that transformation.

`speleodb/utils/sanitize.py` owns both transformations:

- `sanitize_text`: remove tags with `nh3`, decode HTML entities, decompose
  Unicode to NFD, remove combining marks, recompose to NFC, remove
  non-whitespace control/format characters, collapse spaces/tabs, and trim
  edges. Accents are deliberately removed by this variant.
- `sanitize_field_name`: remove tags and decode entities, preserve accents with
  NFC normalization, then apply the same control/whitespace cleanup. Experiment
  field names use this variant through their schema validator.

These functions store plain text, not pre-escaped HTML. Entity decoding and
other ingestion paths make render-side escaping necessary even after a value has
passed a sanitizer. `StationTagSerializer.validate_color` separately requires
six-digit hex colors; frontend validation remains necessary at the rendering
boundary.
