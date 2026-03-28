# -*- coding: utf-8 -*-

from __future__ import annotations

import html
import re
import unicodedata

import nh3

MAX_COMBINING_MARKS_PER_CHAR = 3
"""Legitimate scripts (Thai, Vietnamese, IPA) use up to 3 combining marks
per base character.  Zalgo text stacks 10-50+.  Marks beyond this limit
are silently dropped."""


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
        4. Cap combining marks at ``MAX_COMBINING_MARKS_PER_CHAR`` per base
           character — preserves legitimate accents (``é``, ``ñ``) while
           blocking Zalgo text that stacks 10-50+ marks per character.
        5. NFC recomposition — recombine any remaining valid sequences.
        6. Remove control / format characters (Cc/Cf) except whitespace.
        7. Collapse runs of whitespace and strip edges.

    Example:
        >>> sanitize_text("D̸̨̛͖̯̘̦͔̱̱͖͔̻͖͜ͅa̵̧̡̢̳͓̝̟̩̬̪̻̝̠̻̩̜̫̤...")
        'DaniS'
        >>> sanitize_text('<b>bold</b>')
        'bold'
        >>> sanitize_text('Température')
        'Température'
    """
    if not value:
        return value

    # 1. Strip ALL HTML tags — keeps text content only.
    value = nh3.clean(value, tags=set())

    # 2. Unescape HTML entities that nh3 introduces (e.g. & → &amp;).
    #    We store plain text, not HTML, so entities must be decoded.
    value = html.unescape(value)

    # 3. NFD decomposition — splits precomposed chars into base + marks.
    value = unicodedata.normalize("NFD", value)

    # 4. Cap combining marks per base character (blocks Zalgo, keeps accents).
    #    Marks before any base character are dropped entirely.
    result: list[str] = []
    has_base = False
    mark_count = 0
    for ch in value:
        if unicodedata.category(ch)[0] == "M":
            if has_base:
                mark_count += 1
                if mark_count <= MAX_COMBINING_MARKS_PER_CHAR:
                    result.append(ch)
        else:
            has_base = True
            mark_count = 0
            result.append(ch)
    value = "".join(result)

    # 5. NFC recomposition.
    value = unicodedata.normalize("NFC", value)

    # 6. Remove control / format characters except normal whitespace.
    value = "".join(
        ch
        for ch in value
        if unicodedata.category(ch) not in {"Cc", "Cf"} or ch in "\n\r\t "
    )

    # 7. Normalise whitespace: collapse runs and strip.
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip()
