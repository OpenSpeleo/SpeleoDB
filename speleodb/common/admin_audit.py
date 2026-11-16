"""Request-bound administrator history shared by every registered model admin."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.contrib.admin.views.main import PAGE_VAR
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.utils.text import capfirst

from speleodb.users.models import LogEntry

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.models import Model
    from django.http import HttpRequest
    from django.http import HttpResponse

    from speleodb.users.models import User


class AuditModelAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Replace Django's user-dependent storage without observing model saves."""

    # The supported hooks return our permanent entry instead of Django's model.
    def log_addition(  # type: ignore[override]
        self, request: HttpRequest, obj: Model, message: str | list[dict[str, Any]]
    ) -> LogEntry:
        return LogEntry.record(
            actor_email=cast("User", request.user).email,
            action_flag=LogEntry.Action.ADDITION,
            obj=obj,
            change_message=message,
        )

    def log_change(  # type: ignore[override]
        self, request: HttpRequest, obj: Model, message: str | list[dict[str, Any]]
    ) -> LogEntry:
        return LogEntry.record(
            actor_email=cast("User", request.user).email,
            action_flag=LogEntry.Action.CHANGE,
            obj=obj,
            change_message=message,
        )

    def log_deletions(  # type: ignore[override]
        self, request: HttpRequest, queryset: Iterable[Model]
    ) -> list[LogEntry]:
        return LogEntry.objects.bulk_create(
            [
                LogEntry(
                    actor_email=cast("User", request.user).email,
                    action_flag=LogEntry.Action.DELETION,
                    model_label=obj._meta.label_lower,  # noqa: SLF001
                    object_id=str(obj.pk),
                    object_repr=str(obj)[:200],
                    change_message="Deleted.",
                )
                for obj in queryset
            ]
        )

    def history_view(
        self,
        request: HttpRequest,
        object_id: str,
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            # Django's installed redirect helper is missing from django-stubs.
            return cast(
                "HttpResponse",
                self._get_obj_does_not_exist_redirect(  # type: ignore[attr-defined]
                    request, self.opts, object_id
                ),
            )
        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied
        entries = LogEntry.objects.filter(
            model_label=self.opts.label_lower, object_id=unquote(object_id)
        ).order_by("action_time", "pk")
        paginator = self.get_paginator(request, entries, 100)
        page = paginator.get_page(request.GET.get(PAGE_VAR, 1))
        context = {
            **self.admin_site.each_context(request),
            "title": f"Change history: {obj}",
            "subtitle": None,
            "action_list": page,
            "page_range": paginator.get_elided_page_range(page.number),
            "page_var": PAGE_VAR,
            "pagination_required": paginator.num_pages > 1,
            "module_name": capfirst(self.opts.verbose_name_plural),
            "object": obj,
            "opts": self.opts,
            "preserved_filters": self.get_preserved_filters(request),
            **(extra_context or {}),
        }
        request.current_app = self.admin_site.name
        return TemplateResponse(request, "admin/audit/object_history.html", context)
