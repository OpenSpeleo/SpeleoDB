# Lesson: Never use inline imports

## What happened

When writing test fixtures, I placed `from ... import` statements
inside fixture methods to avoid "polluting" the top-level namespace.
I also used short aliases (`EL`, `LM`, `GV`) to avoid name collisions
that didn't exist.

This violated `docs/coding-rules.md`:
> Never place executable statements (assignments, function calls)
> between import groups.

An inline import inside a function body is the worst form of this --
it scatters imports across the file and hides dependencies.

## Why the self-review missed it

The audit only checked for module-level code between import *groups*
(e.g. an assignment between stdlib and third-party imports). It did
not scan for `import` statements inside functions/methods.

## Rule

ALL imports go at the top of the file in the standard section order.
No exceptions except dynamic `reload()` for testing.

No aliases just to shorten names.

## Prevention

Created `.cursor/rules/python-imports.mdc` so this rule is injected
into every Python editing session automatically.
