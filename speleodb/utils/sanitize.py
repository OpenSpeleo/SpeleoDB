# -*- coding: utf-8 -*-

from __future__ import annotations

import html
import re
import unicodedata

import nh3


def sanitize_text(value: str) -> str:
    """
    Sanitize a user-supplied string for safe storage.

    Pipeline:
        1. Strip **all** HTML tags via ``nh3`` (defense-in-depth against
           stored XSS — the frontend also escapes on display).
        2. Unescape HTML entities (``&amp;`` → ``&``) so plain text with
           ampersands, quotes, etc. is stored as the user typed it.
        3. NFD (canonical) decomposition — splits precomposed characters into
           base + combining marks (e.g. ``é`` → ``e`` + combining-acute)
           without touching compatibility characters (``™``, ``№`` stay).
        4. Strip **all** combining marks (Unicode "Mark" categories Mn/Mc/Me).
        5. NFC recomposition — recombine any remaining valid sequences.
        6. Remove control / format characters (Cc/Cf) except whitespace.
        7. Collapse runs of whitespace and strip edges.

    .. note::

        Accented characters (``é`` → ``e``, ``ñ`` → ``n``) are also
        stripped.  This trade-off keeps the logic simple and safe.

    Example:
        >>> sanitize_text("D̸̨̛͖̯̘̦͔̱̱͖͔̻͖͜ͅa̵̧̡̢̳͓̝̟̩̬̪̻̝̠̻̩̜̫̤...")
        'DaniS'
        >>> sanitize_text('<b>bold</b>')
        'bold'
    """
    if not value:
        return value

    # 1. Strip ALL HTML tags — keeps text content only.
    value = nh3.clean(value, tags=set())

    # 2. Unescape HTML entities that nh3 introduces (e.g. & → &amp;).
    #    We store plain text, not HTML, so entities must be decoded.
    value = html.unescape(value)

    # 2. NFD decomposition — splits precomposed chars into base + marks.
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
