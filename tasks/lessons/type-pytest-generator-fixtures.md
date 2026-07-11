# Type pytest generator fixtures and heterogeneous mappings explicitly

Pytest fixtures containing `yield` are generator functions even when they do not
yield a value to the test. Annotate them as `Generator[None, None, None]`, not
`None`.

For JSON-shaped fixture dictionaries with heterogeneous nested values, add an
explicit nested mapping type (or a `TypedDict`) before iterating over values.
Otherwise mypy may infer each value as `object`, making ordinary key access
invalid.

Run the same full mypy hook used by pre-commit after adding typed test fixtures;
runtime pytest success alone does not validate fixture annotations.
