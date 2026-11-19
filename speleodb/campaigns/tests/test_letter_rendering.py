from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pymupdf

from speleodb.campaigns.letter_rendering import example_letter
from speleodb.campaigns.letter_rendering import render_letter_email
from speleodb.campaigns.letter_rendering import render_letter_pdf
from speleodb.campaigns.models import DonationThankYouTemplate


def test_thank_you_email_escapes_donor_and_explains_attachment_without_images() -> None:
    letter = example_letter(DonationThankYouTemplate(email_subject="Your gift receipt"))
    letter.donor_name = "Atlas & <Crew>"
    letter.amount = Decimal("375.50")
    plain, html = render_letter_email(letter, site_url="https://example.org")
    assert "<title>Your gift receipt</title>" in html
    assert "Atlas &amp; &lt;Crew&gt;" in html
    assert "Atlas & <Crew>" in plain
    assert "$375.50" in plain
    assert "attached as a PDF" in plain


def test_letter_preserves_copyable_gift_reference_and_acknowledgment_id() -> None:
    letter = example_letter(DonationThankYouTemplate())
    letter.donor_name = "García & Co."
    letter.pk = UUID("bbbcffff-a995-4d97-9ce1-ea58424eb876")
    letter.transaction_reference = "wire-office-ff1-01" * 9
    pdf = render_letter_pdf(letter)
    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        text = " ".join(page.get_text() for page in document)
        page = document[0]
        (closing,) = page.search_for("With gratitude,")
        left, right = sorted(
            image["bbox"]
            for image in page.get_image_info()
            if image["bbox"][1] > closing.y0
        )
        (president,) = page.search_for("Alberto Nava")
        (vice_president,) = page.search_for("Jonathan Dekhtiar")
        assert left[0] <= president.x0 < left[2] < right[0]
        assert right[0] <= vice_president.x0 < right[2]
        assert left[1] == right[1]
    assert "García & Co." in text
    assert str(letter.pk) in text
    assert letter.transaction_reference in "".join(text.split())
    assert "preview" not in text.lower()
