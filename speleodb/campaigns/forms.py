"""Explicit campaign test recipient entry."""

from django import forms
from django.core.validators import validate_email


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
