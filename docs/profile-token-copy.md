# Profile application token copying

The account Application Token page provides a Copy button inside the right edge
of the token field. A relative wrapper and absolutely positioned button share
the field's bounds; input padding reserves room for both Copy and Copied!
labels. The field shrinks on narrow screens while the button stays visible. The
field's label targets its input, and copy feedback is announced through a polite
live status.

The page declares the existing `copy-token` Vite controller through inert JSON.
That shared controller reads input/textarea values or text content for existing
integration pages. This keeps clipboard handling in one place without
duplicating credentials in hidden markup or making additional API requests.

Clipboard API access falls back to the existing temporary textarea mechanism
when unavailable or denied. Feedback shows `Copied!` only on success, or
`Failed` on failure, and returns to `Copy` after two seconds. Token refresh is
unchanged.

All site copy buttons use the shared `copy-button` component from
`tailwind_css/shared/design-system.css`: sky-blue background, darker hover,
white text, matching spacing/radius, keyboard focus outline, and disabled state.
It covers token and integration pages, converter result modals, station notes,
and geometry draft copying. Feedback changes labels/icons while keeping info
styling; the shared controller restores each template's original icon.

Conversion-modal button selectors exclude `.copy-button`, and dynamic copy
controls use this class instead of their feature-specific button classes. This
prevents unlayered route CSS from overriding the central component. Context-menu
coordinate items and clickable coordinate table cells retain their respective
menu/table presentation. Styling adds no API calls or runtime scans.

`frontend_common/controllers/copy-token.test.js` exercises the actual page's
controller configuration, input copying, fallback cleanup, failure/retry, empty
values, and existing text-content sources. Run the JavaScript suite, lint, and
clean production asset build in the running application container.
