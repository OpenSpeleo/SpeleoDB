# XSS Escaping Patterns

## Lesson

Stored XSS via `innerHTML` / jQuery `.html()` is easy to introduce and
hard to catch without systematic review. The following patterns must be
followed.

## Rules

1. **Escape at the sink, not the caller.** The function that writes HTML
   is responsible for escaping. Don't rely on callers to pre-escape.

2. **`Utils.raw()` bypasses all protection.** Never wrap template literals
   that interpolate user data in `Utils.raw()`. The escaping inside
   `safeHtml` only applies to direct interpolations, not nested ones
   inside a `raw()` block.

3. **Inline `escapeHtml` copies must stay aligned with `utils.js`.** When
   the canonical `escapeHtml` in `utils.js` changes, all inline copies in
   Django templates must be updated to match (null guard, `String()`
   coercion, quote escaping).

4. **Attribute contexts need quote escaping.** DOM-based `escapeHtml`
   (`textContent` -> `innerHTML`) only escapes `<`, `>`, `&`. We add
   `.replace(/"/g, '&quot;').replace(/'/g, '&#39;')` to also cover
   attribute breakouts.

5. **jQuery `.html()` is the same risk as `innerHTML`.** Use `.text()`
   for plain text messages like error notifications.

6. **Test mocks must match real behavior.** When mocking `escapeHtml` in
   tests, the mock must escape the same characters as the real
   implementation. Divergence hides bugs.

7. **URL attributes need protocol validation.** `href` and `src`
   attributes with API-supplied URLs can execute `javascript:` on click.
   Use `Utils.sanitizeUrl()` to reject non-http(s) schemes. This applies
   to `resource.file`, `resource.miniature`, and `log.attachment`.

8. **CSS color values need validation.** User-controlled color strings
   in `style` attributes can inject arbitrary CSS (e.g.,
   `red; background-image: url(https://evil.com/steal)`). Use
   `Utils.safeCssColor()` which only allows hex `#RGB` / `#RRGGBB`.

9. **`Utils.raw()` with helper return values is fragile.** When a helper
   function returns a plain template literal and that result is consumed
   inside `Utils.raw()`, any unescaped interpolation in the helper is
   silently unsafe. Prefer `Utils.safeHtml` inside the helper, or at
   minimum escape every user-data interpolation explicitly.

## Origin

Full-project XSS audit found 17 unprotected files and 37 partially
protected files. The systemic issue in `ajax_error_modal_management.js`
alone affected 28+ templates.
