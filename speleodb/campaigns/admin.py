"""Explicit superuser review and send actions for campaign mail."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from django import forms
from django.contrib import admin
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import models
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseNotAllowed
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
from speleodb.campaigns.forms import TestEmailForm
from speleodb.campaigns.models import CampaignDismissal
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.operations import TASK_NAME
from speleodb.campaigns.operations import audience
from speleodb.campaigns.operations import review_digest
from speleodb.campaigns.operations import schedule_campaign
from speleodb.users.models import User


class DonationCampaignResource(resources.ModelResource):
    class Meta:
        model = DonationCampaign
        import_id_fields = ("id",)

    def __init__(self, **kwargs: Any) -> None:
        # django-import-export does not annotate this initializer.
        super().__init__(**kwargs)  # type: ignore[no-untyped-call]
        for name in (
            "launched_at",
            "approved_snapshot",
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


@admin.register(DonationCampaign)
class DonationCampaignAdmin(ImportExportModelAdmin):
    resource_classes = [DonationCampaignResource]
    formfield_overrides = {
        models.TextField: {"widget": forms.Textarea(attrs={"rows": 3, "cols": 80})},
    }
    fieldsets = (
        (
            "Campaign",
            {
                "fields": (
                    "headline",
                    "start_date",
                    "end_date",
                    "goal_usd",
                    "goal_currency_label",
                    "goal_message",
                    "donation_url",
                    "reminder_days",
                )
            },
        ),
        (
            "Identity and recipient",
            {
                "fields": (
                    "brand_name",
                    "website_url",
                    "contact_email",
                    "tagline",
                    "recipient_name",
                    "recipient_intro",
                    "tax_deductibility_notice",
                )
            },
        ),
        (
            "Photo",
            {"fields": ("photo", "photo_alt", "photo_credit", "photo_credit_label")},
        ),
        (
            "Dashboard and invitation",
            {
                "fields": (
                    "card_title",
                    "card_summary",
                    "popup_summary",
                    "ownership_promise",
                )
            },
        ),
        (
            "Story view",
            {
                "fields": (
                    "story_kicker",
                    "story_title",
                    "story_summary",
                    "story_cards",
                    "story_goal_label",
                    "story_goal_text",
                    "story_promise",
                )
            },
        ),
        (
            "Buttons and accessibility",
            {
                "fields": (
                    "donate_label",
                    "support_label",
                    "about_label",
                    "story_label",
                    "reminder_label",
                    "back_label",
                    "close_label",
                    "new_tab_label",
                    "dismissal_error",
                    "retry_label",
                )
            },
        ),
        (
            "Email",
            {
                "fields": (
                    "subject",
                    "preheader",
                    "body",
                    "sharing_message",
                    "unsubscribe_label",
                    "send_email",
                )
            },
        ),
        (
            "Submission history",
            {
                "fields": (
                    "launched_at",
                    "approved_snapshot",
                    "creation_date",
                    "modified_date",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    list_display = ("headline", "start_date", "end_date", "launched_at", "send_email")
    readonly_fields = (
        "launched_at",
        "approved_snapshot",
        "creation_date",
        "modified_date",
        "send_email",
    )

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
        return False

    @admin.display(description="Email campaign")
    def send_email(self, obj: DonationCampaign) -> str:
        return format_html(
            '<a href="{}">Send email campaign</a>',
            reverse("admin:campaign_send", args=[obj.pk]),
        )

    def get_urls(self) -> list[Any]:
        return [
            path(
                "<uuid:campaign_id>/send/",
                self.admin_site.admin_view(self.send_view),
                name="campaign_send",
            ),
            # django-import-export extends these URLs without type annotations.
            *super().get_urls(),  # type: ignore[no-untyped-call]
        ]

    def send_view(self, request: HttpRequest, campaign_id: str) -> HttpResponse:
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
        error = ""
        confirmation = None
        if request.method == "POST":
            try:
                receipt = None
                if action == "test" and form.is_valid():
                    receipt = schedule_campaign(
                        str(campaign.pk),
                        requester=request.user,
                        site_url=site_url,
                        test_emails=form.cleaned_data["emails"],
                    )
                elif action == "review":
                    confirmation = signing.dumps(
                        {
                            "campaign": str(campaign.pk),
                            "digest": review_digest(campaign),
                        },
                        salt="campaign-send-review",
                    )
                elif action == "send":
                    review = signing.loads(
                        request.POST.get("confirmation", ""),
                        salt="campaign-send-review",
                        max_age=3600,
                    )
                    if review["campaign"] != str(campaign.pk):
                        raise PermissionDenied("Invalid campaign review.")
                    receipt = schedule_campaign(
                        str(campaign.pk),
                        requester=request.user,
                        site_url=site_url,
                        digest=review["digest"],
                    )
                if receipt:
                    task_url = self.task_results_url(receipt.task_ids)
                    if task_url is not None:
                        return redirect(task_url)
                    error = "Task results are no longer available."
            except (signing.BadSignature, ValueError, KeyError) as exc:
                error = str(exc)
        group_id = campaign.approved_snapshot.get("group_id")
        task_url = None
        if group_id:
            try:
                task_ids = receipt_task_ids(group_id)
            except ValueError:
                # Celery history expires; the permanent launch marker does not.
                task_ids = []
            task_url = self.task_results_url(task_ids)
        return TemplateResponse(
            request,
            "admin/campaigns/send.html",
            {
                **self.admin_site.each_context(request),
                "title": "Send email campaign",
                "campaign": campaign,
                "test_form": form,
                "error": error,
                "confirmation": confirmation,
                "recipient_count": len(audience()),
                "task_results_url": task_url,
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


@admin.register(CampaignDismissal)
class CampaignDismissalAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("user", "campaign", "creation_date", "modified_date")
    list_select_related = ("user", "campaign")
    list_filter = ("campaign",)
    search_fields = ("user__email", "campaign__headline")
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
