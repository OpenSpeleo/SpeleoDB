"""Render the donor's message and its printable gift acknowledgment."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin
from uuid import UUID

import pymupdf
from django.conf import settings
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils import timezone

from speleodb.campaigns.mail import plain_text_from_html
from speleodb.campaigns.models import DonationThankYouLetters

if TYPE_CHECKING:
    from speleodb.campaigns.models import DonationThankYouTemplate

LETTER_ASSETS_DIR = (
    Path(__file__).resolve().parent.parent / "templates/campaigns/letter_assets"
)
LETTER_FONT = LETTER_ASSETS_DIR / "LiberationSans-Regular.ttf"


def example_letter(template: DonationThankYouTemplate) -> DonationThankYouLetters:
    return DonationThankYouLetters(
        id=UUID("20359849-c814-4a46-a2a5-9968bd107052"),
        template=template,
        donor_name="Alex Rivera",
        donor_email="alex@example.org",
        donor_address="100 Sample Street\nExample City, NY 10001",
        amount=Decimal("125.00"),
        gift_date=date(2026, 1, 12),
        payment_method="Wire transfer",
        transaction_reference="WIRE-1042",
    )


def render_letter_email(
    letter: DonationThankYouLetters, *, site_url: str
) -> tuple[str, str]:
    html = render_to_string(
        letter.template.email_template_name,
        {
            "template": letter.template,
            "letter": letter,
            "amount_usd": f"${letter.amount:,.2f}",
            "site_url": site_url,
            "email_assets_url": urljoin(
                site_url, static("campaigns/email_templates/assets/")
            ),
        },
    )
    return plain_text_from_html(html), html


def render_letter_pdf(letter: DonationThankYouLetters) -> bytes:
    html = render_to_string(
        "campaigns/acknowledgment_letter.html",
        {
            "letter": letter,
            "amount_usd": f"${letter.amount:,.2f}",
            "issue_date": timezone.localdate(letter.issued_at),
        },
    )
    # Missing artwork or type must fail issuance before MuPDF can substitute it.
    archive = pymupdf.Archive()  # type: ignore[no-untyped-call]
    for asset in (
        LETTER_FONT,
        settings.BASE_DIR / "frontend_public/static/media/logo-usah-light.png",
        LETTER_ASSETS_DIR / "alberto-nava.png",
        LETTER_ASSETS_DIR / "jonathan-dekhtiar.png",
    ):
        archive.add(asset.read_bytes(), asset.name)  # type: ignore[no-untyped-call]
    story = pymupdf.Story(html=html, archive=archive)  # type: ignore[no-untyped-call]
    page = (0, 0, 612, 792)
    content = (48, 40, 564, 752)
    # Each new rectangle is a fresh US Letter page, so long address blocks
    # continue at reading size instead of shrinking an entire acknowledgment.
    with story.write_with_links(
        lambda _number, _filled: (page, content, None)
    ) as document:  # type: ignore[no-untyped-call]
        if document.page_count > 1:
            for number, sheet in enumerate(document, start=1):
                label = f"Page {number} of {document.page_count}"
                sheet.insert_text(
                    (48, 766),
                    label,
                    fontsize=8,
                    fontname="LiberationSans",
                    fontfile=str(LETTER_FONT),
                )
        document.subset_fonts()
        return bytes(document.tobytes(garbage=4, deflate=True, use_objstms=1))
