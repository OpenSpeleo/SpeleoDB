# Renderer identities need a private namespace

## Failure pattern

An uploaded source identifier is untrusted data, even when the source format
requires identifiers to be unique. Appending a suffix such as `:geometry:0001`
to that value does not create a private namespace: another valid source feature
may already use the derived string.

## Rule

- Assign renderer IDs from deterministic document positions in a namespace the
  producer cannot select.
- Preserve producer IDs separately as source metadata; do not overload them as
  renderer keys.
- When exploding one source feature into several render features, copy its
  source metadata while deriving children only from the renderer-owned base.
- Test a source ID deliberately equal to the old derived-ID shape for every
  supported format adapter.
