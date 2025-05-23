from django.contrib.auth import forms as admin_forms
from django.forms import CharField
from django.forms import EmailField
from django.forms import Form
from django.forms import TextInput

from speleodb.users.models import User


class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.UserCreationForm):
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


def mandatory_field(self) -> None:
    for v in filter(lambda x: x.required, self.fields.values()):
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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def signup(self, request, user) -> None:
        user.name = self.cleaned_data["name"]
        user.country = self.cleaned_data["country"]
        user.save()
