# Name production CSS by product ownership

Migration evidence may refer to the old framework version, but production
filenames, variables, and classes must describe their durable responsibility. A
file named `v3-compat.css` makes an explicit visual contract look temporary and
gives future maintainers no useful ownership boundary.

After parity is established, classify every retained declaration as a product
token, browser normalization, component rule, or semantic utility. Keep the
baseline version in tests and review records, then use production names such as
`design-system.css`, `srgb-*`, `flow-*`, and `row-divide-*`. Do not replace one
historical label with another label such as `legacy-*`.
