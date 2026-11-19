"""Explicit campaign test recipient entry."""

from typing import Any

from django import forms
from django.core.validators import validate_email

from speleodb.campaigns.models import DonationCampaign


class DonorEmailListField(forms.Field):
    widget = forms.Textarea

    def prepare_value(self, value: Any) -> Any:
        if isinstance(value, list):
            return "\n".join(value)
        return value or ""

    def to_python(self, value: Any) -> list[str]:
        return [line.strip() for line in (value or "").splitlines() if line.strip()]


class DonationCampaignForm(forms.ModelForm):  # type: ignore[type-arg]
    donors = DonorEmailListField(
        required=False,
        label="Donors",
        help_text="One email per line. Donors are excluded from campaign emails.",
        widget=forms.Textarea(attrs={"rows": 6, "cols": 60}),
    )

    class Meta:
        model = DonationCampaign
        fields = (
            "donors",
            "goal_usd",
            "donation_url",
            "modal_template",
            "email_main_subject",
            "email_main_template",
            "email_reminder_subject",
            "reminder_email_template",
            "start_date",
            "end_date",
            "reminder_days",
        )


class TestEmailForm(forms.Form):
    emails = forms.CharField(
        widget=forms.Textarea, help_text="Separate addresses with commas or newlines."
    )

    def clean_emails(self) -> list[str]:
        addresses: dict[str, str] = {}
        for value in self.cleaned_data["emails"].replace(",", "\n").splitlines():
            email = value.strip()
            if email:
                validate_email(email)
                addresses.setdefault(email.casefold(), email)
        if not addresses:
            raise forms.ValidationError("Enter at least one email address.")
        return list(addresses.values())


class CampaignAudienceForm(forms.Form):
    project_users_only = forms.BooleanField(
        required=False,
        label="Only users with access to at least one project",
        help_text="Includes direct and team access to any project type.",
    )


class CampaignTemplateSelect(forms.Select):
    template_name = "admin/campaigns/template_select.html"
