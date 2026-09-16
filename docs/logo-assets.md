# Logo assets

The current logo variants live in `frontend_public/static/media/`:

| Asset                 | Intended background | Lettering and icon            | Blue accent                  |
| --------------------- | ------------------- | ----------------------------- | ---------------------------- |
| `logo-sdb-dark.svg`   | Dark                | White (`#ffffff`)             | `#3852fc` (`rgb(56,82,252)`) |
| `logo-sdb-light.svg`  | Light               | Almost-black grey (`#111111`) | `#3852fc` (`rgb(56,82,252)`) |
| `logo-usah-dark.svg`  | Dark                | White (`#ffffff`)             | `#3852fc`                    |
| `logo-usah-light.svg` | Light               | Almost-black grey (`#111111`) | `#3852fc`                    |

All variants use the same blue accent and transparent background. Each
dark/light pair has identical dimensions, viewBox, and artwork geometry. The
SpeleoDB assets measure `738.72 × 162`; the USAH Institute assets measure
`1006.45 × 162` to accommodate the longer wordmark without compressing it. The
background designation determines the foreground color, not the accent.

The USAH variants replace the main wordmark with `USAH Institute`: `USAH` uses
the foreground color and `Institute` uses blue. They preserve the original cave
icon and `Explore as One. Survey as Many` tagline, including its Roboto
Condensed outlines. Both words use Meedori Sans Light (weight 300), matching the
original wordmark at an effective 90px font size with approximately 6.25px
tracking. This typeface uses capital-height glyphs even for lowercase letters,
with case-specific stencil forms. The A and H in `USAH` use the complete
lowercase `a`/`h` alternates: A has its crossbar and H has both full vertical
stems. The displayed name remains `USAH Institute`.

The font is by Meedori Studio / Danilo De Marco; see the
[original designer project](https://www.behance.net/gallery/25629097/Meedori-Sans-Free-Font).
The Light font was obtained from
[Befonts](https://befonts.com/meedori-sans-font.html), whose listing permits
personal and commercial use. New lettering is converted to SVG paths, so the
assets require no installed or remotely loaded fonts.

The light variant preserves the embedded icon bytes and recolors its alpha
silhouette using an SVG flood/composite filter. This keeps the asset standalone
and requires no JavaScript, additional requests, or image dependencies.

Verify SVG parsing, matching dimensions and path geometry, the shared blue
accent, each variant's foreground color, preserved embedded image, and
alpha-preserving filtering when updating these assets. Also render USAH variants
on their intended backgrounds to check spacing and clipping, and confirm four
foreground letter paths and nine blue letter paths.
