# -*- coding: utf-8 -*-

from __future__ import annotations

import unicodedata

from speleodb.utils.sanitize import sanitize_text


class TestSanitizeText:
    """Test cases for the sanitize_text utility function."""

    # ------------------------------------------------------------------
    # Zalgo / combining-mark abuse
    # ------------------------------------------------------------------

    def test_zalgo_text_reduced_to_near_base_characters(self) -> None:
        """Heavily decorated zalgo text should have excess marks stripped."""
        zalgo = (
            "D\u0338\u0328\u031b\u0356\u032f\u0318\u0326\u0354\u0331\u0331\u0356"
            "\u0354\u033b\u0356\u035c\u0345a\u0335\u0327\u0321\u0322\u0333\u0353"
            "\u031d\u031f\u0329\u032c\u032a\u033b\u031d\u0320\u033b\u0329\u031c"
            "\u032b\u0324\u0312\u033e\u0302\u030b\u0300\u0304\u030c\u0313\u0313"
            "\u0306\u0310\u030e\u030b\u031b\u0306\u0310\u0314\u030c\u0308\u0301"
            "\u0315\u0312\u0301\u0309\u0315n\u0334\u0321\u0327\u0328\u032c\u0330"
            "\u035a\u0356\u031e\u0349\u0318\u0349\u0326\u0333\u035a\u034e\u032a"
            "\u0320\u0323\u0354\u0356\u032e\u0329\u032d\u031f\u0324\u030b\u030b"
            "\u0306\u0308\u0301\u030e\u0308\u0301\u030b\u0301\u0305\u0313\u0304"
            "\u0306\u0308\u030b\u0318\u030b\u030f\u030b\u0315\u0308\u030b\u031b"
            "i\u0335\u0327\u0328\u0327\u0328\u0329\u032c\u032d\u0333\u031f\u032c"
            "\u035a\u031e\u0339\u0318\u031d\u0331\u0320\u033a\u033a\u031e\u034d"
            "\u0319\u0356\u0302\u0307\u030b\u0300\u033f\u0302\u030b\u033d\u0314"
            "\u0309\u0302\u033d\u0312\u0315\u030e\u030b\u0315S\u0338\u0356\u0348"
            "\u032b\u0349\u0354\u0333\u0330\u0318\u0347\u0347\u031c\u0310\u0310"
            "\u033f\u0308\u0302\u0301\u0315\u030a\u030d\u0308\u0302\u030a\u0301"
            "\u033d\u0303\u0300\u0345"
        )
        result = sanitize_text(zalgo)
        # Base characters survive; excess marks are stripped
        base_only = "".join(c for c in result if unicodedata.category(c)[0] != "M")
        assert base_only == "DaniS"
        # Each base char keeps at most 3 combining marks
        mark_count = len(result) - len(base_only)
        assert mark_count <= len(base_only) * 3

    def test_simple_combining_accent_preserved(self) -> None:
        """A single combining acute accent on 'e' should be kept."""
        # 'e' + combining acute accent (U+0301) → recomposed to 'é'
        assert sanitize_text("e\u0301") == "é"

    def test_precomposed_accent_preserved(self) -> None:
        """Pre-composed é should survive sanitization."""
        assert sanitize_text("\u00e9") == "é"

    # ------------------------------------------------------------------
    # Compatibility characters preserved (NFD, not NFKD)
    # ------------------------------------------------------------------

    def test_ligature_preserved(self) -> None:
        """Ligature ﬁ is a compatibility character and should be preserved."""
        assert sanitize_text("\ufb01le") == "\ufb01le"

    def test_fullwidth_ascii_preserved(self) -> None:
        """Fullwidth latin letters are compatibility characters and preserved."""
        assert (
            sanitize_text("\uff28\uff45\uff4c\uff4c\uff4f")
            == "\uff28\uff45\uff4c\uff4c\uff4f"
        )

    def test_trademark_preserved(self) -> None:
        """™ (U+2122) should not be decomposed to TM."""
        assert sanitize_text("Fleet™") == "Fleet™"

    def test_numero_sign_preserved(self) -> None:
        """№ (U+2116) should not be decomposed to No."""
        assert sanitize_text("Станция №1") == "Станция №1"

    # ------------------------------------------------------------------
    # Accented characters are preserved (up to 3 marks per base char)
    # ------------------------------------------------------------------

    def test_accented_latin_preserved(self) -> None:
        """Common accented Latin letters keep their diacritics."""
        assert sanitize_text("café") == "café"
        assert sanitize_text("naïve") == "naïve"
        assert sanitize_text("résumé") == "résumé"

    def test_n_tilde_preserved(self) -> None:
        """ñ should survive sanitization."""
        assert sanitize_text("niño") == "niño"

    def test_devanagari_marks_preserved(self) -> None:
        """Devanagari combining marks within the limit are preserved."""
        assert sanitize_text("स्टेशन") == "स्टेशन"

    # ------------------------------------------------------------------
    # Control / format characters
    # ------------------------------------------------------------------

    def test_zero_width_characters_removed(self) -> None:
        """Zero-width joiners, non-joiners, and spaces should be stripped."""
        text = "ab\u200b\u200c\u200dcd"  # ZWSP, ZWNJ, ZWJ
        assert sanitize_text(text) == "abcd"

    def test_normal_whitespace_preserved(self) -> None:
        """Regular spaces, tabs, and newlines should remain."""
        assert sanitize_text("hello world") == "hello world"
        assert sanitize_text("hello\tworld") == "hello world"  # tab → space
        assert sanitize_text("hello\nworld") == "hello\nworld"

    def test_direction_override_characters_removed(self) -> None:
        """Bidi override characters (Cf category) should be stripped."""
        text = "hello\u202eworld"
        assert sanitize_text(text) == "helloworld"

    # ------------------------------------------------------------------
    # Whitespace handling
    # ------------------------------------------------------------------

    def test_leading_trailing_whitespace_stripped(self) -> None:
        """Leading and trailing spaces should be removed."""
        assert sanitize_text("  hello  ") == "hello"

    def test_multiple_spaces_collapsed(self) -> None:
        """Runs of spaces should collapse into a single space."""
        assert sanitize_text("hello     world") == "hello world"

    def test_mixed_whitespace_collapsed(self) -> None:
        """Tabs mixed with spaces collapse to a single space."""
        assert sanitize_text("hello \t  world") == "hello world"

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_empty_string_returns_empty(self) -> None:
        assert sanitize_text("") == ""

    def test_plain_ascii_unchanged(self) -> None:
        """An already-clean string should pass through unchanged."""
        assert sanitize_text("SpeleoDB") == "SpeleoDB"

    def test_only_combining_marks_returns_empty(self) -> None:
        """A string of nothing but combining marks should become empty."""
        marks_only = "\u0300\u0301\u0302\u0303\u0304"
        assert sanitize_text(marks_only) == ""

    def test_emoji_preserved(self) -> None:
        """Common emoji should survive sanitisation."""
        assert sanitize_text("Cave 🦇") == "Cave 🦇"

    def test_cjk_characters_preserved(self) -> None:
        """CJK characters should not be affected."""
        assert sanitize_text("洞窟探検") == "洞窟探検"

    def test_cyrillic_preserved(self) -> None:
        """Cyrillic base characters are preserved."""
        assert sanitize_text("Москва Moscow") == "Москва Moscow"

    def test_numbers_and_punctuation_preserved(self) -> None:
        """Digits and common punctuation are not affected."""
        assert sanitize_text("Station #42 — depth: 120m") == "Station #42 — depth: 120m"

    def test_real_world_cave_name(self) -> None:
        """A typical cave name stays clean."""
        assert sanitize_text("Grotte de la Luire") == "Grotte de la Luire"

    # ------------------------------------------------------------------
    # HTML tag stripping (nh3)
    # ------------------------------------------------------------------

    def test_script_tag_and_content_stripped(self) -> None:
        """<script> tags AND their content are removed entirely by nh3."""
        assert sanitize_text('<script>alert("xss")</script>') == ""

    def test_script_tag_surrounding_text_preserved(self) -> None:
        """Text around <script> tags survives; only the script block is removed."""
        result = sanitize_text('Before <script>alert("xss")</script> After')
        assert "<script>" not in result
        assert "alert" not in result
        assert "Before" in result
        assert "After" in result

    def test_img_onerror_stripped(self) -> None:
        """<img> with event handler is stripped entirely (void element, no text)."""
        assert sanitize_text("<img onerror=alert(1)>") == ""

    def test_bold_tag_stripped(self) -> None:
        """<b> tags are stripped but text content is kept."""
        assert sanitize_text("<b>bold</b>") == "bold"

    def test_nested_tags_stripped(self) -> None:
        """Nested tags are all removed, only text survives."""
        assert sanitize_text("<div><p>text</p></div>") == "text"

    def test_anchor_tag_stripped(self) -> None:
        """<a> tags with href are stripped, link text is kept."""
        assert sanitize_text('<a href="https://evil.com">click</a>') == "click"

    def test_angle_brackets_in_plain_text_stripped(self) -> None:
        """Angle brackets that look like tags are removed."""
        result = sanitize_text("<WIP> Station Name")
        assert "<" not in result
        assert ">" not in result

    def test_html_with_attributes_stripped(self) -> None:
        """Tags with class/style/data attributes are fully removed."""
        assert (
            sanitize_text('<div class="evil" style="background:url(x)">safe</div>')
            == "safe"
        )

    def test_mixed_html_and_text(self) -> None:
        """HTML mixed with clean text keeps only the text parts."""
        assert sanitize_text("Hello <b>world</b>!") == "Hello world!"

    def test_plain_ampersand_preserved(self) -> None:
        """Bare ampersands in text survive the pipeline."""
        assert sanitize_text("A & B") == "A & B"
