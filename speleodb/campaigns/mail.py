"""File-based campaign mail with links to account preferences."""

from __future__ import annotations

from html import unescape
from typing import Any
from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.mail import mailers
from django.template import engines
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import strip_tags

CONTENT_FIELDS = (
    "email_main_subject",
    "email_reminder_subject",
    "goal_usd",
    "donation_url",
    "email_main_template",
    "reminder_email_template",
)


def render_message(
    campaign: dict[str, Any], *, site_url: str, unsubscribe: str
) -> tuple[str, str]:
    context = {
        "campaign": campaign,
        "site_url": site_url,
        "email_assets_url": urljoin(
            site_url, static("campaigns/email_templates/assets/")
        ),
        "unsubscribe_url": unsubscribe,
    }
    # Render the reviewed source, so file edits cannot change queued messages.
    template = engines["django"].from_string(campaign["email_template_source"])
    html = template.render(context)
    # Head metadata and responsive email CSS do not belong in the text alternative.
    body_html = html.split("</head>", 1)[-1]
    plain = "\n".join(
        line.strip()
        for line in unescape(strip_tags(body_html)).splitlines()
        if line.strip()
    )
    plain += f"\n\n{campaign['donation_url']}\n\nUnsubscribe: {unsubscribe}\n"
    return plain, html


def send_message(
    campaign: dict[str, Any], *, email: str, site_url: str
) -> dict[str, Any]:
    unsubscribe = urljoin(site_url, reverse("private:user_preferences"))
    plain, html = render_message(campaign, site_url=site_url, unsubscribe=unsubscribe)
    message = EmailMultiAlternatives(
        subject=campaign["subject"],
        body=plain,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
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
        }
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
