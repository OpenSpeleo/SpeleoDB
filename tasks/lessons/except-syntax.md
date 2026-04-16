# Lesson: except syntax — bare commas, parentheses only with `as`

## What happened

An agent added unnecessary parentheses to `except ValueError, TypeError:`
in `speleodb/api/v2/views/gis_view.py`, changing it to
`except (ValueError, TypeError):`. This is wrong — the project uses
Python 3.14+ and deliberately uses PEP 758 bare-comma syntax.

The agent then wrote a cursor rule that enforced the **opposite** of
what the project wants. This mistake recurred because the agent assumed
the parenthesized form was always correct without reading `pyproject.toml`
(`requires-python = ">=3.14,<3.15"`).

## Rule

- `except ValueError, TypeError:` — correct (bare comma, no binding)
- `except (ValueError, TypeError) as e:` — correct (parentheses needed for `as`)
- `except (ValueError, TypeError):` — WRONG (unnecessary parentheses)

## Prevention

Rewrote `.cursor/rules/except-syntax.mdc` to match the actual project
convention: bare commas by default, parentheses only when `as e` is used.
