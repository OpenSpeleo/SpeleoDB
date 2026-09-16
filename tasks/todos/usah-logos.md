# USAH Institute logos

- [x] Inspect existing logo geometry, typography, and palette.
- [x] Obtain the matching Meedori Sans Light outlines and compose USAH
      Institute.
- [x] Create dark/light SVG variants, retaining the existing icon and tagline.
- [x] Render and inspect both variants; validate in the application container.
- [x] Document asset names, palette, typography, and verification results.

Use the original wordmark's Meedori Sans Light typography and spacing. Keep
`USAH` white on dark backgrounds and `#111111` on light backgrounds, and use
`#3852fc` for `Institute` in both. Preserve the existing icon and tagline;
expand the canvas if needed to avoid distorting the longer wordmark.

## Review

- [x] Replace stencil A/H with complete capital-height a/h alternates in both
      variants and inspect the browser preview. Do not run tests, per user
      request.

The corrected preview shows the A crossbar and both full H stems on dark and
light backgrounds. No tests were run for this correction.

Created both standalone SVGs at 1006.45 × 162 with outlined Meedori Sans Light
lettering, matching the original effective 90px size and approximately 6.25px
tracking. The icon and tagline retain their original artwork and placement.
Chrome previews on dark and white backgrounds were visually inspected: no
clipping, matching typography, and the requested color split.

Container SVG checks passed for all 13 new glyphs, palette, pair geometry,
preserved tagline and embedded icon, filter references, and absence of font
dependencies. Before the A/H correction, the container JavaScript suite passed
all 1,032 tests across 62 files. Documentation and whitespace checks passed.
