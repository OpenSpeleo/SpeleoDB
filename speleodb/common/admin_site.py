"""Admin navigation and routes for immediate background operations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from django.contrib.admin import AdminSite
from django.contrib.admin.views.autocomplete import AutocompleteJsonView
from django.urls import path
from django.urls import reverse

from speleodb.background_jobs import operation_views
from speleodb.surveys.models import Project

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models import Model
    from django.http import HttpRequest
    from django.http import HttpResponse
    from django.urls import URLPattern
    from django.urls import URLResolver


class ProjectAutocompleteJsonView(AutocompleteJsonView):
    def serialize_result(self, obj: Model, to_field_name: str) -> dict[str, str]:
        result = super().serialize_result(obj, to_field_name)
        if isinstance(obj, Project):
            result["text"] = f"{obj.name} ({obj.pk})"
        return result


class SpeleoDBAdminSite(AdminSite):
    def autocomplete_view(self, request: HttpRequest) -> HttpResponse:
        # View.as_view has a broad response annotation; this view returns JSON.
        return cast(
            "HttpResponse",
            ProjectAutocompleteJsonView.as_view(admin_site=self)(request),
        )

    def get_urls(self) -> list[URLPattern | URLResolver]:
        return [
            path("operations/", self.admin_view(self.operations), name="operations"),
            path(
                "operations/confirm/",
                self.admin_view(self.confirm_operation),
                name="operations_confirm",
            ),
            path(
                "operations/receipt/",
                self.admin_view(self.operation_receipt),
                name="operations_receipt",
            ),
            path(
                "operations/rerun/<uuid:task_id>/",
                self.admin_view(self.rerun_operation),
                name="operations_rerun",
            ),
            *super().get_urls(),
        ]

    def operations(self, request: HttpRequest) -> HttpResponse:
        return operation_views.operations(self, request)

    def confirm_operation(self, request: HttpRequest) -> HttpResponse:
        return operation_views.confirm_operation(self, request)

    def operation_receipt(self, request: HttpRequest) -> HttpResponse:
        return operation_views.operation_receipt(self, request)

    def rerun_operation(self, request: HttpRequest, task_id: UUID) -> HttpResponse:
        return operation_views.rerun_operation(self, request, task_id)

    def get_app_list(
        self, request: HttpRequest, app_label: str | None = None
    ) -> list[dict[str, Any]]:
        # Model ownership and URLs remain unchanged; only navigation is grouped.
        apps = super().get_app_list(request)
        grouped: list[dict[str, Any]] = []
        remaining: list[dict[str, Any]] = []
        for app in apps:
            if app["app_label"] in {"background_jobs", "django_celery_results"}:
                grouped.extend(app["models"])
            else:
                remaining.append(app)
        if request.user.is_active and request.user.is_superuser:
            grouped.insert(
                0,
                {
                    "name": "Operations",
                    "object_name": "Operations",
                    "perms": {"view": True},
                    "admin_url": reverse("admin:operations"),
                    "add_url": None,
                    "view_only": True,
                },
            )
        if grouped:
            order = {
                "Operations": 0,
                "BackgroundJob": 1,
                "TaskResult": 2,
                "GroupResult": 3,
            }
            for model in grouped:
                if model["object_name"] == "BackgroundJob":
                    model["name"] = "Export jobs"
            remaining.append(
                {
                    "name": "Background operations",
                    "app_label": "background_jobs",
                    "app_url": reverse(
                        "admin:app_list", kwargs={"app_label": "background_jobs"}
                    ),
                    "has_module_perms": True,
                    "models": sorted(
                        grouped, key=lambda model: order.get(model["object_name"], 4)
                    ),
                }
            )
        if app_label is not None:
            # The original technical app index remains a useful alias.
            target = (
                "background_jobs" if app_label == "django_celery_results" else app_label
            )
            return [app for app in remaining if app["app_label"] == target]
        return sorted(remaining, key=lambda app: app["name"].lower())
