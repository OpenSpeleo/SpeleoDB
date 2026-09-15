"""Single-answer confirmation for optional interactive management commands."""

from __future__ import annotations


def confirm_command(prompt: str) -> bool:
    """Proceed only on an explicit Y; empty, invalid, or closed input cancels."""
    try:
        return input(prompt).strip().upper() == "Y"
    except EOFError:
        return False
