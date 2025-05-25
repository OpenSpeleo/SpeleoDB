from typing import Any

from django.contrib.auth import forms as admin_forms
from django.forms import CharField
from django.forms import EmailField
from django.forms import Form
from django.forms import TextInput
from django.http import HttpRequest

from speleodb.users.models import User


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
        fields = ("email",)
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
        user.name = self.cleaned_data["name"]
        user.country = self.cleaned_data["country"]
        user.save()
