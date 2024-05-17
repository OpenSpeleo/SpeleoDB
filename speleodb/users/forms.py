from allauth.account.forms import SignupForm
from allauth.utils import set_form_field_order
from django.contrib.auth import forms as admin_forms
from django.forms import CharField
from django.forms import EmailField
from django.forms import TextInput
from django.utils.translation import gettext_lazy as _

from speleodb.users.models import User


class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):
        model = User
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.UserCreationForm):
    """
    Form for User Creation in the Admin Area.
    To change user signup, see UserSignupForm.
    """

    class Meta(admin_forms.UserCreationForm.Meta):
        model = User
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }


class UserSignupForm(SignupForm):
    """
    Form that will be rendered on a user sign up section/screen.
    Default fields will be added automatically.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"] = CharField(
            label=_("Full Name"),
            max_length=255,
            min_length=5,
            required=True,
            widget=TextInput(attrs={"placeholder": _("Full Name")}),
        )
        set_form_field_order(self, ["email", "name", "password1", "password2"])

    def save(self, request):
        user = super().save(request=request)
        user.name = self.cleaned_data.get("name")
        user.save()
        return user
