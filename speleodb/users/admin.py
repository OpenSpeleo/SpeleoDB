# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from allauth.account.admin import EmailAddressAdmin as _EmailAddressAdmin
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth.decorators import login_required
from django.db import transaction
from import_export import resources
from import_export.admin import ExportMixin
from rest_framework.authtoken.admin import TokenAdmin as _TokenAdmin
from rest_framework.authtoken.models import TokenProxy

from speleodb.users.forms import UserAdminChangeForm
from speleodb.users.forms import UserAdminCreationForm
from speleodb.users.models import AccountEvent
from speleodb.users.models import LogEntry
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.users.models import User
from speleodb.utils.admin_filters import SurveyTeamCountryFilter
from speleodb.utils.admin_filters import UserCountryFilter

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.forms.models import ModelForm
    from django.http import HttpRequest


if settings.DJANGO_ADMIN_FORCE_ALLAUTH:
    # Force the `admin` sign in process to go through the `django-allauth` workflow:
    # https://docs.allauth.org/en/latest/common/admin.html#admin
    admin.site.login = login_required(admin.site.login)


class UserImportExportResource(resources.ModelResource):
    class Meta:
        model = User
        # optional, only specified fields gets exported, else all the fields
        # fields = ('id', 'price', 'description')

        # optional, describes how order of export
        # export_order = ('id', 'description', 'price')


class UserAdminBase(ExportMixin, auth_admin.UserAdmin):  # type: ignore[type-arg,misc]
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
                    "is_beta_tester",
                    "has_api_doc_access",
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
        "is_beta_tester",
        "has_api_doc_access",
        "date_joined",
        "last_login",
    ]
    search_fields = ["name", "email"]
    ordering = ["-last_login"]
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_beta_tester",
        "has_api_doc_access",
        "is_active",
        "groups",
        UserCountryFilter,
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "password1", "password2"),
            },
        ),
    )

    resource_class = UserImportExportResource  # type: ignore[assignment]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_change_permission(
        self, request: HttpRequest, obj: User | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_delete_permission(
        self, request: HttpRequest, obj: User | None = None
    ) -> bool:
        return request.user.is_superuser


if "hijack" in settings.INSTALLED_APPS:
    from hijack.contrib.admin import HijackUserAdminMixin

    @admin.register(User)
    class UserAdmin(HijackUserAdminMixin, UserAdminBase):  # type: ignore[misc]
        def get_hijack_user(self, obj: User) -> User:
            return obj

        def get_changelist_instance(self, request: HttpRequest) -> Any:
            if not request.user.is_superuser:
                return super(HijackUserAdminMixin, self).get_changelist_instance(
                    request
                )
            return super().get_changelist_instance(request)  # type: ignore[no-untyped-call]

else:

    @admin.register(User)
    class UserAdmin(UserAdminBase):  # type: ignore[no-redef]
        pass


admin.site.unregister(EmailAddress)


@admin.register(EmailAddress)
class EmailAddressAdmin(_EmailAddressAdmin):
    autocomplete_fields: tuple[str] = ("user",)  # type: ignore[misc]

    @admin.action(description="Mark selected email addresses as verified")
    @transaction.atomic
    def make_verified(
        self, request: HttpRequest, queryset: QuerySet[EmailAddress]
    ) -> None:
        candidate_ids = list(
            queryset.filter(verified=False).values_list("pk", flat=True)
        )
        super().make_verified(request, queryset)
        for address in queryset.filter(pk__in=candidate_ids, verified=True):
            self.log_change(request, address, "Marked email address as verified.")

    def get_form(  # type: ignore[override]
        self, request: HttpRequest, obj: EmailAddress | None = None, **kwargs: Any
    ) -> type[ModelForm]:  # type: ignore[type-arg]
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["user"].widget.attrs["style"] = "width: 20em;"  # pyright: ignore[reportAttributeAccessIssue]
        return form

    def has_add_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_change_permission(
        self, request: HttpRequest, obj: EmailAddress | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_delete_permission(
        self, request: HttpRequest, obj: EmailAddress | None = None
    ) -> bool:
        return request.user.is_superuser


@admin.register(SurveyTeam)
class SurveyTeamAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("id", "name", "country", "creation_date", "modified_date")
    ordering = ("name",)
    list_filter = ["creation_date", SurveyTeamCountryFilter]


@admin.register(SurveyTeamMembership)
class SurveyTeamMembershipAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "team",
        "user",
        "role",
        "creation_date",
        "modified_date",
        "is_active",
    )
    ordering = ("team",)
    list_filter = ["is_active", "role"]

    def save_model(
        self,
        request: HttpRequest,
        obj: SurveyTeamMembership,
        form: Any,
        change: bool,
    ) -> None:
        super().save_model(request, obj, form, change)

        # Refresh the `modified_date` field
        obj.team.save()


@admin.register(AccountEvent)
class AccountEventAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "id",
        "user",
        "action",
        "application",
        "ip_addr",
        "creation_date",
    )
    list_filter = ("action", "application", "creation_date")
    search_fields = ("user__email", "user__name", "ip_addr", "user_agent")
    ordering = ("-creation_date",)
    readonly_fields = (
        "id",
        "user",
        "action",
        "application",
        "ip_addr",
        "user_agent",
        "creation_date",
        "modified_date",
    )
    fields = readonly_fields

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:

        if obj is not None:
            return False
        return request.user.is_superuser

    def has_delete_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return request.user.is_superuser


# ---------------------------------------------------------------------------
# Token admin -- superuser-only, completely hidden from staff
# ---------------------------------------------------------------------------

admin.site.unregister(TokenProxy)


@admin.register(TokenProxy)
class TokenAdmin(_TokenAdmin):
    def has_module_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_view_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_add_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_change_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:

        if obj is not None:
            return False
        return request.user.is_superuser

    def has_delete_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return request.user.is_superuser


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    # to have a date-based drilldown navigation in the admin page
    date_hierarchy = "action_time"

    # Filter by the actor and model snapshots, and the action classification.
    list_filter = ["actor_email", "model_label", "action_flag"]

    # when searching the user will be able to search in both object_repr and
    # change_message
    search_fields = ["actor_email", "object_id", "object_repr", "change_message"]

    list_display = [
        "action_time",
        "actor_email",
        "model_label",
        "action_flag",
        "object_repr",
        "get_change_message",
    ]
    readonly_fields = (
        "action_time",
        "actor_email",
        "model_label",
        "object_id",
        "object_repr",
        "action_flag",
        "get_change_message",
        "details",
    )
    fields = readonly_fields
    actions = None

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: LogEntry | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: LogEntry | None = None
    ) -> bool:
        return False
