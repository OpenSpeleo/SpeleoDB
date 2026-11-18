"""Fixed campaign templates and account-bound unsubscribe links."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.core.mail import mailers
from django.template.loader import render_to_string
from django.urls import reverse

UNSUBSCRIBE_SALT = "campaign-updates-unsubscribe"
CONTENT_FIELDS = (
    "brand_name",
    "contact_email",
    "website_url",
    "tagline",
    "card_title",
    "card_summary",
    "goal_currency_label",
    "goal_message",
    "ownership_promise",
    "donate_label",
    "about_label",
    "story_label",
    "reminder_label",
    "back_label",
    "close_label",
    "new_tab_label",
    "retry_label",
    "dismissal_error",
    "recipient_intro",
    "support_label",
    "sharing_message",
    "unsubscribe_label",
    "photo_credit_label",
    "story_kicker",
    "story_title",
    "story_summary",
    "story_goal_label",
    "story_goal_text",
    "story_promise",
    "story_cards",
    "reminder_days",
    "recipient_name",
    "tax_deductibility_notice",
    "photo_alt",
    "photo_credit",
    "headline",
    "subject",
    "preheader",
    "body",
    "popup_summary",
    "goal_usd",
    "donation_url",
)


def unsubscribe_url(site_url: str, user_id: str, email: str) -> str:
    token = signing.dumps({"user_id": user_id, "email": email}, salt=UNSUBSCRIBE_SALT)
    return urljoin(site_url, reverse("campaigns:unsubscribe", args=[token]))


def render_message(
    campaign: dict[str, Any], *, site_url: str, unsubscribe: str
) -> tuple[str, str]:
    context = {
        "campaign": campaign,
        "site_url": site_url,
        "photo_url": urljoin(site_url, campaign["photo_url"])
        if campaign.get("photo_url")
        else "",
        "unsubscribe_url": unsubscribe,
    }
    return (
        render_to_string("campaigns/email.txt", context),
        render_to_string("campaigns/email.html", context),
    )


def send_message(
    campaign: dict[str, Any], *, email: str, site_url: str, user_id: str | None
) -> dict[str, Any]:
    unsubscribe = (
        unsubscribe_url(site_url, user_id, email)
        if user_id
        else urljoin(site_url, reverse("campaigns:test-unsubscribe"))
    )
    plain, html = render_message(campaign, site_url=site_url, unsubscribe=unsubscribe)
    headers = {}
    if user_id:
        headers = {
            "List-Unsubscribe": f"<{unsubscribe}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
    message = EmailMultiAlternatives(
        subject=("" if user_id else "[TEST] ") + campaign["subject"],
        body=plain,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
        reply_to=[campaign["contact_email"]] if campaign.get("contact_email") else [],
        headers=headers,
    )
    message.attach_alternative(html, "text/html")
    # Anymail supports these extension attributes on Django's native messages.
    message.track_clicks = False  # type: ignore[attr-defined]
    message.track_opens = False  # type: ignore[attr-defined]
    if (
        settings.MAILERS["default"]["BACKEND"]
        == "anymail.backends.mailersend.EmailBackend"
    ):
        message.esp_extra = {  # type: ignore[attr-defined]
            "settings": {
                "track_clicks": False,
                "track_opens": False,
                "track_content": False,
            },
            **({"list_unsubscribe": unsubscribe} if user_id else {}),
        }
        # MailerSend's dedicated API field generates the RFC 8058 headers.
        message.extra_headers = {}
    sent = mailers["default"].send_messages([message])
    status = getattr(message, "anymail_status", None)
    if status is not None:
        recipient = status.recipients.get(email)
        if recipient is None or recipient.status not in {"sent", "queued"}:
            raise RuntimeError(
                "Provider did not accept campaign email: "
                f"{getattr(recipient, 'status', 'unknown')}"
            )
        return {
            "outcome": "provider-accepted",
            "message_id": str(recipient.message_id or ""),
        }
    if sent != 1:
        raise RuntimeError("Email backend did not accept the message.")
    return {"outcome": "backend-accepted"}
