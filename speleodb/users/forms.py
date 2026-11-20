# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import urlsplit

from allauth.idp.oidc.models import Client
from django.conf import settings
from django.contrib.auth import forms as admin_forms
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.forms import CharField
from django.forms import EmailField
from django.forms import Form
from django.forms import ModelForm
from django.forms import TextInput

from speleodb.users.models import User
from speleodb.utils.user_identity import validate_user_name

if TYPE_CHECKING:
    from django.http import HttpRequest


class OIDCClientForm(ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = Client
        fields = ("name", "type", "redirect_uris")

    def clean_redirect_uris(self) -> str:
        value: str = self.cleaned_data["redirect_uris"]
        urls = [line.strip() for line in value.splitlines() if line.strip()]
        if not urls:
            raise ValidationError("Register at least one callback URL.")
        client_type = self.cleaned_data.get("type", self.instance.type)
        for url in urls:
            # RFC 8252 private-use redirects use a reverse-domain scheme and one
            # slash. Only public clients can register them.
            if client_type == Client.Type.PUBLIC and re.fullmatch(
                r"[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+:/[a-zA-Z0-9._~%-][a-zA-Z0-9._~/%-]*",
                url,
            ):
                continue
            URLValidator(schemes=["http", "https"])(url)
            parsed = urlsplit(url)
            try:
                # urlsplit validates the port range when this property is read.
                _ = parsed.port
            except ValueError as exc:
                raise ValidationError(
                    "Register a callback URL with a valid port."
                ) from exc
            local_callback = settings.DEBUG and parsed.hostname in {"127.0.0.1", "::1"}
            if client_type == Client.Type.PUBLIC and settings.DEBUG:
                local_callback = local_callback or parsed.hostname == "localhost"
            if (
                (parsed.scheme != "https" and not local_callback)
                or parsed.fragment
                or parsed.username is not None
                or "*" in url
            ):
                raise ValidationError(
                    "Register an exact HTTPS callback URL. Local development also "
                    "allows HTTP loopback callbacks."
                )
        return "\n".join(urls)


class UserAdminChangeForm(admin_forms.UserChangeForm):  # type:ignore[type-arg]
    class Meta:
        model = User
        fields = "__all__"
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.UserCreationForm):  # type:ignore[type-arg]
    """
    Form for User Creation in the Admin Area.
    To change user signup, see UserSignupForm.
    """

    class Meta:
        model = User
        fields = ("email", "name")
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": "This email has already been taken."},
        }


def mandatory_field(form: Form) -> None:
    for v in filter(lambda x: x.required, form.fields.values()):
        v.label = str(v.label) + "*"


class SignupForm(Form):
    name = CharField(
        label="Full Name",
        max_length=255,
        min_length=5,
        required=True,
        validators=[validate_user_name],
        widget=TextInput(attrs={"placeholder": "Full Name"}),
    )

    country = CharField(
        label="Country",
        max_length=2,
        min_length=2,
        required=True,
        widget=TextInput(attrs={"placeholder": "Country"}),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def signup(self, request: HttpRequest, user: User) -> None:
        """Required allauth hook; AccountAdapter populates fields before saving."""
