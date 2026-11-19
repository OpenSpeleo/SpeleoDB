"""Private donor acknowledgments in Django admin."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING
from typing import Any

from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse
from django.http import Http404
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

from speleodb.campaigns.letter_operations import issue_letter
from speleodb.campaigns.letter_operations import letter_review_digest
from speleodb.campaigns.letter_operations import regenerate_letter
from speleodb.campaigns.letter_operations import resend_letter
from speleodb.campaigns.letter_operations import schedule_letter_preview
from speleodb.campaigns.letter_rendering import render_letter_pdf
from speleodb.campaigns.models import DonationThankYouLetters
from speleodb.campaigns.models import DonationThankYouTemplate
from speleodb.campaigns.preview_admin import SavePreviewAdmin
from speleodb.users.models import User

if TYPE_CHECKING:
    from uuid import UUID

    from django import forms
    from django.db.models import QuerySet
    from django.http import HttpRequest


def task_result_url(task_id: str) -> str | None:
    result_id = (
        TaskResult.objects.filter(task_id=task_id).values_list("pk", flat=True).first()
    )
    if result_id is None:
        return None
    return reverse("admin:django_celery_results_taskresult_change", args=[result_id])


class DonationAcknowledgmentAdmin(SavePreviewAdmin):
    def has_module_permission(self, request: HttpRequest) -> bool:
        return bool(request.user.is_active and request.user.is_superuser)

    def has_view_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return self.has_module_permission(request)

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return self.has_module_permission(request)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return self.has_module_permission(request)

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return self.has_module_permission(request)

    def preview_response(
        self,
        request: HttpRequest,
        obj: DonationThankYouLetters | DonationThankYouTemplate,
    ) -> JsonResponse:
        if not isinstance(request.user, User):
            raise PermissionDenied
        task_id = schedule_letter_preview(
            obj, requester=request.user, site_url=request.build_absolute_uri("/")
        )
        return JsonResponse(
            {
                "message": f"Saved. Preview email requested for {request.user.email}.",
                "change_url": reverse(
                    f"admin:campaigns_{self.opts.model_name}_change", args=[obj.pk]
                ),
                "task_results_url": task_result_url(task_id),
            }
        )


class DonationThankYouTemplateAdmin(DonationAcknowledgmentAdmin):
    preview_fields = ("email_template",)
    list_display = ("name", "email_subject")
    fields = ("name", "email_subject", "email_template")


class DonationThankYouLettersAdmin(DonationAcknowledgmentAdmin):
    preview_fields = ("template",)
    change_form_template = "admin/campaigns/letter_change_form.html"
    actions = None
    list_display = (
        "donor_name",
        "donor_email",
        "amount",
        "gift_date",
        "transaction_reference",
        "issued_at",
        "last_sent_at",
    )
    search_fields = ("donor_name", "donor_email", "transaction_reference")
    list_filter = ("issued_at",)
    readonly_fields = ("issued_at", "last_sent_at", "delivery_status")
    fieldsets = (
        (None, {"fields": ("template",)}),
        ("Donor", {"fields": ("donor_name", "donor_email", "donor_address")}),
        (
            "Gift",
            {
                "fields": (
                    "amount",
                    "gift_date",
                    "payment_method",
                    "transaction_reference",
                )
            },
        ),
    )

    def get_fieldsets(
        self, request: HttpRequest, obj: DonationThankYouLetters | None = None
    ) -> list[Any]:
        sections = list(self.fieldsets)
        if obj and obj.issued_at:
            sections.append(
                (
                    "Delivery",
                    {"fields": ("issued_at", "last_sent_at", "delivery_status")},
                )
            )
        return sections

    def get_form(
        self,
        request: HttpRequest,
        obj: DonationThankYouLetters | None = None,
        change: bool = False,
        **kwargs: Any,
    ) -> type[forms.ModelForm[Any]]:
        # Letter forms use a normal selector; preview actions live in the footer.
        kwargs["formfield_callback"] = partial(
            admin.ModelAdmin.formfield_for_dbfield, self, request=request
        )
        form = super().get_form(request, obj, change=change, **kwargs)
        template_field = form.base_fields["template"]
        if isinstance(template_field.widget, RelatedFieldWidgetWrapper):
            template_field.widget = template_field.widget.widget
        return form

    def has_delete_permission(
        self, request: HttpRequest, obj: DonationThankYouLetters | None = None
    ) -> bool:
        return super().has_delete_permission(request, obj) and (
            obj is None or not obj.issued_at
        )

    def save_model(
        self,
        request: HttpRequest,
        obj: DonationThankYouLetters,
        form: forms.ModelForm[DonationThankYouLetters],
        change: bool,
    ) -> None:
        if obj.issued_at:
            raise PermissionDenied("Reopen the issued letter to regenerate its PDF.")
        super().save_model(request, obj, form, change)

    def get_queryset(self, request: HttpRequest) -> QuerySet[DonationThankYouLetters]:
        queryset = super().get_queryset(request)
        if (
            request.method == "POST"
            and request.resolver_match
            and request.resolver_match.url_name
            in {
                "campaigns_donationthankyouletters_change",
                "campaigns_donationthankyouletters_delete",
            }
        ):
            # Native change/delete forms own a transaction. Check editability on the
            # current row so an open draft form cannot overwrite an issued letter.
            return queryset.select_for_update()
        return queryset

    @admin.display(description="Latest delivery task")
    def delivery_status(self, obj: DonationThankYouLetters) -> str:
        url = task_result_url(str(obj.last_task_id)) if obj.last_task_id else None
        return (
            format_html('<a href="{}">View delivery status</a>', url)
            if url
            else "Unavailable"
        )

    def saved_action_response(
        self, request: HttpRequest, obj: DonationThankYouLetters
    ) -> HttpResponse | None:
        if "_preview_pdf" in request.POST:
            return JsonResponse(
                {
                    "change_url": reverse(
                        "admin:campaigns_donationthankyouletters_change", args=[obj.pk]
                    ),
                    "pdf_url": reverse("admin:letter_pdf", args=[obj.pk]),
                }
            )
        if "_review_letter" in request.POST:
            return redirect("admin:letter_issue", pk=obj.pk)
        return super().saved_action_response(request, obj)

    def get_urls(self) -> list[Any]:
        return [
            path(
                "<uuid:pk>/pdf/",
                self.admin_site.admin_view(self.pdf_view),
                name="letter_pdf",
            ),
            # Issuance owns the transaction that connects the S3 archive to its row.
            path(
                "<uuid:pk>/issue/",
                transaction.non_atomic_requests(
                    self.admin_site.admin_view(self.issue_view)
                ),
                name="letter_issue",
            ),
            path(
                "<uuid:pk>/regenerate/",
                transaction.non_atomic_requests(
                    self.admin_site.admin_view(self.regenerate_view)
                ),
                name="letter_regenerate",
            ),
            path(
                "<uuid:pk>/resend/",
                self.admin_site.admin_view(self.resend_view),
                name="letter_resend",
            ),
            *super().get_urls(),
        ]

    def get_letter(self, request: HttpRequest, pk: UUID) -> DonationThankYouLetters:
        if not self.has_view_permission(request):
            raise PermissionDenied
        return get_object_or_404(
            DonationThankYouLetters.objects.select_related("template"),
            pk=pk,
        )

    def pdf_view(self, request: HttpRequest, pk: UUID) -> HttpResponse | FileResponse:
        letter = self.get_letter(request, pk)
        if request.method != "GET":
            return HttpResponseNotAllowed(["GET"])
        filename = f"acknowledgment-{letter.pk}.pdf"
        if letter.issued_at:
            if not letter.pdf:
                raise Http404("The archived acknowledgment is unavailable.")
            # FileResponse owns this open file until Django finishes streaming it.
            return FileResponse(
                letter.pdf.open("rb"),
                as_attachment=True,
                filename=filename,
                content_type="application/pdf",
            )
        return HttpResponse(
            render_letter_pdf(letter),
            content_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    def issue_view(self, request: HttpRequest, pk: UUID) -> HttpResponse:
        letter = self.get_letter(request, pk)
        if not isinstance(request.user, User):
            raise PermissionDenied
        if request.method not in {"GET", "POST"}:
            return HttpResponseNotAllowed(["GET", "POST"])
        url = reverse("admin:campaigns_donationthankyouletters_change", args=[pk])
        if letter.issued_at:
            self.message_user(
                request, "This letter was already issued.", messages.WARNING
            )
            return redirect(url)
        error = ""
        salt = "donation-letter-issue"
        if request.method == "POST":
            try:
                digest = signing.loads(
                    request.POST.get("confirmation", ""), salt=salt, max_age=3600
                )
                task_id = issue_letter(
                    letter,
                    requester=request.user,
                    site_url=request.build_absolute_uri("/"),
                    expected_digest=digest,
                )
            except signing.BadSignature:
                error = "Review the current gift details and confirm again."
            except ValidationError as exc:
                error = " ".join(exc.messages)
            except ValueError as exc:
                error = str(exc)
            else:
                task_result = TaskResult.objects.get(task_id=task_id)
                return redirect(
                    "admin:django_celery_results_taskresult_change", task_result.pk
                )
            letter.refresh_from_db()
        return TemplateResponse(
            request,
            "admin/campaigns/letter_issue.html",
            {
                **self.admin_site.each_context(request),
                "title": "Issue donation acknowledgment",
                "letter": letter,
                "confirmation": signing.dumps(letter_review_digest(letter), salt=salt),
                "error": error,
                "change_url": url,
            },
        )

    def regenerate_view(self, request: HttpRequest, pk: UUID) -> HttpResponse:
        letter = self.get_letter(request, pk)
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not letter.issued_at:
            self.message_user(
                request, "Issue the acknowledgment first.", messages.ERROR
            )
            return redirect("admin:campaigns_donationthankyouletters_change", pk)

        form_class = self.get_form(request, letter, change=True)
        form = form_class(request.POST, request.FILES, instance=letter)
        if not form.is_valid():
            return self.changeform_view(request, object_id=str(pk))
        updated = form.save(commit=False)
        regenerate_letter(updated)
        self.log_change(request, updated, "Regenerated the issued acknowledgment PDF.")
        self.message_user(request, "Acknowledgment saved and PDF regenerated.")
        return redirect("admin:campaigns_donationthankyouletters_change", pk)

    def resend_view(self, request: HttpRequest, pk: UUID) -> HttpResponse:
        letter = self.get_letter(request, pk)
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not isinstance(request.user, User):
            raise PermissionDenied
        try:
            resend_letter(
                letter, requester=request.user, site_url=request.build_absolute_uri("/")
            )
        except ValueError as exc:
            self.message_user(request, str(exc), messages.ERROR)
        else:
            self.message_user(
                request, "Delivery of the archived acknowledgment requested."
            )
        return redirect("admin:campaigns_donationthankyouletters_change", pk)
