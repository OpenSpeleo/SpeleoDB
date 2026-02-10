# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import unicodedata


def sanitize_text(value: str) -> str:
    """
    Sanitize a Unicode string by removing all combining marks.

    This protects against "zalgo text" and other Unicode abuse where combining
    diacritical marks are stacked on characters to produce unreadable glyphs.

    Steps:
        1. NFD (canonical) decomposition — splits precomposed characters into
           base + combining marks (e.g. ``é`` → ``e`` + combining-acute)
           without touching compatibility characters (``™``, ``№`` stay).
        2. Strip **all** combining marks (Unicode "Mark" categories Mn/Mc/Me).
        3. NFC recomposition — recombine any remaining valid sequences.
        4. Remove control / format characters (Cc/Cf) except whitespace.
        5. Collapse runs of whitespace and strip edges.

    .. note::

        Accented characters (``é`` → ``e``, ``ñ`` → ``n``) are also
        stripped.  This trade-off keeps the logic simple and safe.

    Example:
        >>> sanitize_text("D̸̨̛͖̯̘̦͔̱̱͖͔̻͖͜ͅa̵̧̡̢̳͓̝̟̩̬̪̻̝̠̻̩̜̫̤...")
        'DaniS'
    """
    if not value:
        return value

    # 1. NFD decomposition — splits precomposed chars into base + marks.
    #    Unlike NFKD, does NOT expand compatibility chars (™, №, ﬁ stay).
    value = unicodedata.normalize("NFD", value)

    # 2. Strip ALL combining marks.
    value = "".join(ch for ch in value if unicodedata.category(ch)[0] != "M")

    # 3. NFC recomposition.
    value = unicodedata.normalize("NFC", value)

    # 4. Remove control / format characters except normal whitespace.
    value = "".join(
        ch
        for ch in value
        if unicodedata.category(ch) not in {"Cc", "Cf"} or ch in "\n\r\t "
    )

    # 5. Normalise whitespace: collapse runs and strip.
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip()
