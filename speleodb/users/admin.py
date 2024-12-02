from allauth.account.admin import EmailAddressAdmin as _EmailAddressAdmin
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth.decorators import login_required
from dynamic_raw_id.admin import DynamicRawIDMixin
from hijack.contrib.admin import HijackUserAdminMixin

from speleodb.users.forms import UserAdminChangeForm
from speleodb.users.forms import UserAdminCreationForm
from speleodb.users.models import User

if settings.DJANGO_ADMIN_FORCE_ALLAUTH:
    # Force the `admin` sign in process to go through the `django-allauth` workflow:
    # https://docs.allauth.org/en/latest/common/admin.html#admin
    admin.site.login = login_required(admin.site.login)  # type: ignore[method-assign]


@admin.register(User)
class UserAdmin(HijackUserAdminMixin, auth_admin.UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {"fields": ("name", "country")},
        ),
        (
            "Preferences",
            {"fields": ("email_on_speleodb_updates", "email_on_projects_updates")},
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    list_display = [
        "email",
        "name",
        "country",
        "is_superuser",
        "is_staff",
        "date_joined",
        "last_login",
    ]
    search_fields = ["name", "email"]
    ordering = ["email"]
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )

    def get_hijack_user(self, obj):
        return obj


class EmailAddressAdmin(DynamicRawIDMixin, _EmailAddressAdmin):
    dynamic_raw_id_fields = ("user",)
    raw_id_fields = ()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["user"].widget.attrs["style"] = "width: 20em;"
        return form


admin.site.unregister(EmailAddress)
admin.site.register(EmailAddress, EmailAddressAdmin)
