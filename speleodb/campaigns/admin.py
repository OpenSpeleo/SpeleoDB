"""Explicit superuser review and send actions for campaign mail."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

from django.contrib import admin
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseNotAllowed
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.urls import reverse
from django.utils.html import format_html
from django_celery_results.models import TaskResult
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from speleodb.background_jobs.operations import receipt_task_ids
from speleodb.campaigns.forms import CampaignAudienceForm
from speleodb.campaigns.forms import CampaignTemplateSelect
from speleodb.campaigns.forms import DonationCampaignForm
from speleodb.campaigns.forms import TestEmailForm
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignDismissal
from speleodb.campaigns.models import DonationCampaignEmail
from speleodb.campaigns.operations import TASK_NAME
from speleodb.campaigns.operations import audience
from speleodb.campaigns.operations import review_digest
from speleodb.campaigns.operations import schedule_campaign
from speleodb.users.models import User

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django import forms
    from django.db import models


class DonationCampaignResource(resources.ModelResource):
    class Meta:
        model = DonationCampaign
        import_id_fields = ("id",)

    def __init__(self, **kwargs: Any) -> None:
        # django-import-export does not annotate this initializer.
        super().__init__(**kwargs)  # type: ignore[no-untyped-call]
        for name in (
            "creation_date",
            "modified_date",
        ):
            self.fields[name].readonly = True

    def before_save_instance(
        self, instance: DonationCampaign, row: Any, **kwargs: Any
    ) -> None:
        instance.full_clean(
            exclude=[name for name, field in self.fields.items() if field.readonly]
        )
        if DonationCampaign.objects.exclude(pk=instance.pk).exists():
            raise ValidationError("Only one donation campaign is allowed.")


class DonationCampaignEmailInline(admin.TabularInline):  # type: ignore[type-arg]
    model = DonationCampaignEmail
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ("creation_date", "email_type", "subject", "recipient_count", "template")
    readonly_fields = fields

    @admin.display(description="Recipients")
    def recipient_count(self, obj: DonationCampaignEmail) -> int:
        return len(obj.recipients)

    def has_view_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return bool(request.user.is_active and request.user.is_superuser)

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(DonationCampaign)
class DonationCampaignAdmin(ImportExportModelAdmin):
    form = DonationCampaignForm
    resource_classes = [DonationCampaignResource]
    inlines = (DonationCampaignEmailInline,)
    change_form_template = "admin/campaigns/change_form.html"
    import_export_change_list_template = "admin/campaigns/change_list.html"
    fieldsets = (
        (
            "Campaign",
            {
                "fields": (
                    "goal_usd",
                    "donation_url",
                    "donors",
                    "modal_template",
                )
            },
        ),
        (
            "Main email",
            {
                "fields": (
                    "email_main_subject",
                    "email_main_template",
                    "send_email",
                )
            },
        ),
        (
            "Reminder email",
            {
                "fields": (
                    "email_reminder_subject",
                    "reminder_email_template",
                    "send_reminder_email",
                )
            },
        ),
        (
            "Schedule",
            {"fields": ("start_date", "end_date", "reminder_days")},
        ),
        (
            "Audit dates",
            {"fields": ("creation_date", "modified_date"), "classes": ("collapse",)},
        ),
    )

    list_display = (
        "email_main_subject",
        "start_date",
        "end_date",
        "send_email",
        "send_reminder_email",
    )
    readonly_fields = (
        "creation_date",
        "modified_date",
        "send_email",
        "send_reminder_email",
    )

    def formfield_for_choice_field(
        self, db_field: models.Field[Any, Any], request: HttpRequest, **kwargs: Any
    ) -> forms.TypedChoiceField | None:
        if db_field.name in {"email_main_template", "reminder_email_template"}:
            kwargs["widget"] = CampaignTemplateSelect
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def changeform_view(
        self,
        request: HttpRequest,
        object_id: str | None = None,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        preview = request.method == "POST" and "_save_preview" in request.POST
        if preview:
            if not self.has_change_permission(request) or not isinstance(
                request.user, User
            ):
                raise PermissionDenied
            if request.POST["_save_preview"] not in {
                "email_main_template",
                "reminder_email_template",
            }:
                return JsonResponse(
                    {"message": "Choose a valid preview template."}, status=400
                )
            try:
                validate_email(request.user.email)
            except ValidationError:
                return JsonResponse(
                    {"message": "Set a valid account email address first."},
                    status=400,
                )
            if request.POST[
                "_save_preview"
            ] == "reminder_email_template" and not request.POST.get(
                "reminder_email_template"
            ):
                return JsonResponse(
                    {
                        "message": "Select a reminder email template first.",
                        "errors": {
                            "reminder_email_template": [
                                "Select a reminder email template."
                            ]
                        },
                    },
                    status=400,
                )
        # Native admin owns validation, save hooks, audit logging and the transaction.
        response = super().changeform_view(request, object_id, form_url, extra_context)
        if preview and isinstance(response, TemplateResponse) and response.context_data:
            form = response.context_data["adminform"].form
            return JsonResponse(
                {
                    "message": "Correct the form errors before requesting a preview.",
                    "errors": {
                        name: list(errors) for name, errors in form.errors.items()
                    },
                },
                status=400,
            )
        return response

    def preview_response(
        self, request: HttpRequest, obj: DonationCampaign
    ) -> JsonResponse:
        if not isinstance(request.user, User):
            raise PermissionDenied
        receipt = schedule_campaign(
            str(obj.pk),
            requester=request.user,
            site_url=request.build_absolute_uri("/"),
            test_emails=[request.user.email],
            reminder=request.POST["_save_preview"] == "reminder_email_template",
        )
        return JsonResponse(
            {
                "message": f"Saved. Preview email requested for {request.user.email}.",
                "change_url": reverse(
                    "admin:campaigns_donationcampaign_change", args=[obj.pk]
                ),
                "task_results_url": self.task_results_url(receipt.task_ids),
            }
        )

    def response_change(
        self, request: HttpRequest, obj: DonationCampaign
    ) -> HttpResponse:
        if "_save_preview" in request.POST:
            return self.preview_response(request, obj)
        return super().response_change(request, obj)

    def response_add(
        self,
        request: HttpRequest,
        obj: DonationCampaign,
        post_url_continue: str | None = None,
    ) -> HttpResponse:
        if "_save_preview" in request.POST:
            return self.preview_response(request, obj)
        return super().response_add(request, obj, post_url_continue)

    def has_import_permission(self, request: HttpRequest) -> bool:
        return self.has_change_permission(request)

    def has_export_permission(self, request: HttpRequest) -> bool:
        return self.has_change_permission(request)

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return bool(request.user.is_active and request.user.is_superuser)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return (
            self.has_change_permission(request)
            and not DonationCampaign.objects.exists()
        )

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return self.has_change_permission(request, obj)

    def get_deleted_objects(
        self,
        objs: Sequence[DonationCampaign] | models.QuerySet[DonationCampaign],
        request: HttpRequest,
    ) -> tuple[list[Any], dict[str, int], set[str], list[Any]]:
        deleted_objects, model_count, perms_needed, protected = (
            super().get_deleted_objects(objs, request)
        )
        if self.has_delete_permission(request):
            # History is deleted with its campaign, but cannot be deleted on its own.
            perms_needed.discard(
                DonationCampaignEmail._meta.verbose_name  # noqa: SLF001 - Django model metadata.
            )
        return deleted_objects, model_count, perms_needed, protected

    @admin.display(description="Send email")
    def send_email(self, obj: DonationCampaign) -> str:
        if obj._state.adding:  # noqa: SLF001 - Django persisted-object state.
            return "Save the campaign to enable email actions."
        return format_html(
            '<button type="submit" class="button" form="campaign-send-{}">'
            "Send Email Campaign</button>",
            obj.pk,
        )

    @admin.display(description="Send reminder email")
    def send_reminder_email(self, obj: DonationCampaign) -> str:
        if obj._state.adding:  # noqa: SLF001 - Django persisted-object state.
            return "Save the campaign to enable email actions."
        if obj.reminder_email_template and obj.email_reminder_subject.strip():
            return format_html(
                '<button type="submit" class="button" form="campaign-send-reminder-{}">'
                "Send Reminder Email Campaign</button>",
                obj.pk,
            )
        return format_html(
            '<button type="button" class="button" disabled>'
            "Send Reminder Email Campaign</button>"
            '<p class="help">{}</p>',
            "Select and save a reminder email template and subject "
            "to enable this action.",
        )

    def get_urls(self) -> list[Any]:
        return [
            path(
                "<uuid:campaign_id>/send/",
                self.admin_site.admin_view(self.send_view),
                name="campaign_send",
            ),
            path(
                "<uuid:campaign_id>/send-reminder/",
                self.admin_site.admin_view(self.send_view),
                {"reminder": True},
                name="campaign_send_reminder",
            ),
            # django-import-export extends these URLs without type annotations.
            *super().get_urls(),  # type: ignore[no-untyped-call]
        ]

    def send_view(
        self, request: HttpRequest, campaign_id: str, *, reminder: bool = False
    ) -> HttpResponse:
        if not self.has_change_permission(request) or not isinstance(
            request.user, User
        ):
            raise PermissionDenied
        if request.method not in {"GET", "POST"}:
            return HttpResponseNotAllowed(["GET", "POST"])
        campaign = get_object_or_404(DonationCampaign, pk=campaign_id)
        site_url = request.build_absolute_uri("/")
        action = request.POST.get("action")
        form = TestEmailForm(request.POST if action == "test" else None)
        audience_form = CampaignAudienceForm(
            request.POST if action in {"review", "send"} else None
        )
        project_users_only = (
            audience_form.cleaned_data["project_users_only"]
            if audience_form.is_bound and audience_form.is_valid()
            else False
        )
        reminder_unconfigured = reminder and (
            not campaign.reminder_email_template
            or not campaign.email_reminder_subject.strip()
        )
        error = ""
        if reminder and not campaign.reminder_email_template:
            error = "Select and save a reminder email template before sending."
        elif reminder and not campaign.email_reminder_subject.strip():
            error = "Enter and save a reminder email subject before sending."
        confirmation = None
        if request.method == "POST" and not reminder_unconfigured:
            try:
                receipt = None
                if action == "test" and form.is_valid():
                    receipt = schedule_campaign(
                        str(campaign.pk),
                        requester=request.user,
                        site_url=site_url,
                        test_emails=form.cleaned_data["emails"],
                        reminder=reminder,
                    )
                elif action == "review":
                    confirmation = signing.dumps(
                        {
                            "campaign": str(campaign.pk),
                            "send_id": str(uuid4()),
                            "digest": review_digest(
                                campaign,
                                reminder=reminder,
                                project_users_only=project_users_only,
                            ),
                            "reminder": reminder,
                            "project_users_only": project_users_only,
                        },
                        salt="campaign-send-review",
                    )
                elif action == "send":
                    review = signing.loads(
                        request.POST.get("confirmation", ""),
                        salt="campaign-send-review",
                        max_age=3600,
                    )
                    if (
                        review["campaign"] != str(campaign.pk)
                        or review["reminder"] != reminder
                    ):
                        raise PermissionDenied("Invalid campaign review.")
                    receipt = schedule_campaign(
                        str(campaign.pk),
                        requester=request.user,
                        site_url=site_url,
                        digest=review["digest"],
                        send_id=review["send_id"],
                        reminder=reminder,
                        project_users_only=project_users_only,
                    )
                if receipt:
                    task_url = self.task_results_url(receipt.task_ids)
                    if task_url is not None:
                        return redirect(task_url)
                    error = "Task results are no longer available."
            except (signing.BadSignature, ValueError, KeyError) as exc:
                error = str(exc)
        history = DonationCampaignEmail.objects.filter(
            campaign=campaign,
            email_type=(
                DonationCampaignEmail.EmailType.REMINDER
                if reminder
                else DonationCampaignEmail.EmailType.MAIN
            ),
        ).order_by("-creation_date")
        return TemplateResponse(
            request,
            "admin/campaigns/send.html",
            {
                **self.admin_site.each_context(request),
                "title": "Send Reminder Email Campaign"
                if reminder
                else "Send Email Campaign",
                "send_history": history,
                "reminder_unconfigured": reminder_unconfigured,
                "email_subject": (
                    campaign.email_reminder_subject
                    if reminder
                    else campaign.email_main_subject
                ),
                "selected_template": (
                    campaign.reminder_email_template
                    if reminder
                    else campaign.email_main_template
                ),
                "campaign": campaign,
                "test_form": form,
                "error": error,
                "confirmation": confirmation,
                "recipient_count": len(
                    audience(campaign, project_users_only=project_users_only)
                ),
                "audience_form": audience_form,
                "project_users_only": project_users_only,
            },
        )

    @staticmethod
    def task_results_url(task_ids: list[str]) -> str | None:
        result_ids = list(
            TaskResult.objects.filter(task_id__in=task_ids, task_name=TASK_NAME)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        if not result_ids:
            return None
        if len(result_ids) == 1:
            return reverse(
                "admin:django_celery_results_taskresult_change", args=[result_ids[0]]
            )
        return (
            reverse("admin:django_celery_results_taskresult_changelist")
            + "?"
            + urlencode({"pk__in": ",".join(str(pk) for pk in result_ids)})
        )


@admin.register(DonationCampaignDismissal)
class DonationCampaignDismissalAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("user", "campaign", "creation_date", "modified_date")
    list_select_related = ("user", "campaign")
    list_filter = ("campaign",)
    search_fields = ("user__email", "campaign__email_main_subject")
    ordering = ("-modified_date",)
    readonly_fields = ("id", "user", "campaign", "creation_date", "modified_date")

    def has_module_permission(self, request: HttpRequest) -> bool:
        return bool(request.user.is_active and request.user.is_superuser)

    def has_view_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return self.has_module_permission(request)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return self.has_module_permission(request)


@admin.register(DonationCampaignEmail)
class DonationCampaignEmailAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "creation_date",
        "campaign",
        "email_type",
        "subject",
        "recipient_count",
    )
    list_select_related = ("campaign",)
    list_filter = ("email_type", "campaign")
    search_fields = ("subject", "campaign__email_main_subject")
    ordering = ("-creation_date",)
    readonly_fields = (
        "id",
        "campaign",
        "email_type",
        "subject",
        "template",
        "recipients",
        "creation_date",
        "modified_date",
        "task_results_link",
    )

    @admin.display(description="Recipients")
    def recipient_count(self, obj: DonationCampaignEmail) -> int:
        return len(obj.recipients)

    @admin.display(description="Task results")
    def task_results_link(self, obj: DonationCampaignEmail) -> str:
        try:
            task_ids = receipt_task_ids(str(obj.pk))
        except ValueError:
            return "Task results are no longer available."
        task_url = DonationCampaignAdmin.task_results_url(task_ids)
        if task_url is None:
            return "Task results are no longer available."
        return format_html('<a href="{}">View task results</a>', task_url)

    def has_module_permission(self, request: HttpRequest) -> bool:
        return bool(request.user.is_active and request.user.is_superuser)

    def has_view_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return self.has_module_permission(request)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False
