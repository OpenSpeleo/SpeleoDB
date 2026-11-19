"""Shared native admin save and email preview flow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.template.response import TemplateResponse

from speleodb.campaigns.forms import CampaignTemplateSelect
from speleodb.users.models import User

if TYPE_CHECKING:
    from django import forms
    from django.db import models
    from django.http import HttpRequest
    from django.http import HttpResponse


class SavePreviewAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    preview_fields: tuple[str, ...]
    change_form_template = "admin/campaigns/change_form.html"

    def formfield_for_dbfield(
        self, db_field: models.Field[Any, Any], request: HttpRequest, **kwargs: Any
    ) -> forms.Field | None:
        if db_field.name in self.preview_fields:
            kwargs["widget"] = CampaignTemplateSelect
        return super().formfield_for_dbfield(db_field, request, **kwargs)

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
            if request.POST["_save_preview"] not in self.preview_fields:
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
        if (
            request.method == "POST"
            and (preview or "_preview_pdf" in request.POST)
            and isinstance(response, TemplateResponse)
            and response.context_data
        ):
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

    def saved_action_response(
        self, request: HttpRequest, obj: Any
    ) -> HttpResponse | None:
        if "_save_preview" in request.POST:
            return self.preview_response(request, obj)
        return None

    def preview_response(self, request: HttpRequest, obj: Any) -> JsonResponse:
        raise NotImplementedError

    def response_change(self, request: HttpRequest, obj: Any) -> HttpResponse:
        if response := self.saved_action_response(request, obj):
            return response
        return super().response_change(request, obj)

    def response_add(
        self,
        request: HttpRequest,
        obj: Any,
        post_url_continue: str | None = None,
    ) -> HttpResponse:
        if response := self.saved_action_response(request, obj):
            return response
        return super().response_add(request, obj, post_url_continue)
