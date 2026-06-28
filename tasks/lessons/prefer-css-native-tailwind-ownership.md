# Prefer CSS-Native Tailwind Ownership

## Pattern

Do not confuse configuration consolidation with delivery consolidation. If the
product goal is to reunify public and private Tailwind, success means one
generated production Tailwind asset and one build/watch pipeline—not merely two
entrypoints importing the same configuration foundation. State that acceptance
criterion explicitly before implementation.

When one side is explicitly selected as the visual reference, import that
CSS-native reference unchanged from the single production entrypoint. Give the
other surface durable component names rather than redefining shared selectors
such as `.btn`, `.h1`, or `.form-input`. This keeps the reference cascade
immutable while allowing the secondary surface to converge on its tokens.

When Tailwind 4 entrypoints differ only in a small set of theme values, do not
duplicate complete JavaScript configurations. Put shared tokens and plugin
registration in the imported design-system stylesheet and keep only genuine
visual differences as narrow `@theme inline` blocks in the owning entrypoint.

Use `inline` when replacing legacy JavaScript theme extensions whose emitted
literal declarations are already a product contract. This can preserve the
generated utility byte-for-byte while still removing the legacy configuration
surface.

Do not add a `.dark` class merely to announce that a document is dark. Use the
standard `color-scheme` metadata/property. A public document that also loads a
private stylesheet can unintentionally activate private class-controlled dark
variants if `.dark` is added to its root.

## Verification

- Freeze clean generated output before moving configuration ownership.
- Compare unminified outputs first; require every difference to be intentional.
- Compile union-source sentinels and prove unsupported nested trees stay out.
- Compile the private reference independently and require its ordinary rules to
  remain an exact subsequence of the unified output; compiler-owned variable
  initializers may only expand by declaration superset.
- Test every independent document root and require the product asset exactly
  once, including public GIS.
- Treat running watcher output as untrusted until a clean build reproduces it.
