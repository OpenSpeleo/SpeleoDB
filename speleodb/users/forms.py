# from allauth.account.forms import SignupForm
# from allauth.utils import set_form_field_order
from django.contrib.auth import forms as admin_forms
from django.forms import CharField
from django.forms import EmailField
from django.forms import Form
from django.forms import TextInput

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
            "email": {"unique": "This email has already been taken."},
        }


# class UserSignupForm(SignupForm):
#     """
#     Form that will be rendered on a user sign up section/screen.
#     Default fields will be added automatically.
#     """

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.fields["name"] = CharField(
#             label="Full Name",
#             max_length=255,
#             min_length=5,
#             required=True,
#             widget=TextInput(attrs={"placeholder": "Full Name"}),
#         )
#         set_form_field_order(self, ["email", "name", "password1", "password2"])

#     def save(self, request):
#         user = super().save(request=request)
#         user.name = self.cleaned_data.get("name")
#         user.save()
#         return user


def mandatory_field(self):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def signup(self, request, user):
        print(self.cleaned_data)
        user.name = self.cleaned_data["name"]
        user.country = self.cleaned_data["country"]
        user.save()
