# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.contrib.auth import forms as admin_forms
from django.forms import CharField
from django.forms import EmailField
from django.forms import Form
from django.forms import TextInput

from speleodb.users.models import User
from speleodb.utils.user_identity import validate_user_name

if TYPE_CHECKING:
    from django.http import HttpRequest


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
