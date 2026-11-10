"""Superuser-only server-rendered operations and execution receipts."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from django.contrib import messages
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django_celery_results.models import TaskResult

from speleodb.background_jobs.operation_forms import AllGeoJSONForm
from speleodb.background_jobs.operation_forms import ProjectGeoJSONForm
from speleodb.background_jobs.operation_forms import ProjectOperationForm
from speleodb.background_jobs.operations import TASK_NAMES
from speleodb.background_jobs.operations import eligible_projects
from speleodb.background_jobs.operations import get_operation_parameters
from speleodb.background_jobs.operations import receipt_task_ids
from speleodb.background_jobs.operations import schedule_operation
from speleodb.common.enums import TaskResultStatus
from speleodb.surveys.models import Project
from speleodb.users.models import User

if TYPE_CHECKING:
    from django.contrib.admin import AdminSite
    from django.http import HttpRequest
    from django.http import HttpResponse

    from speleodb.background_jobs.operations import OperationReceipt

CONFIRMATION_SALT = "admin-history-reset"


def _operator(request: HttpRequest) -> User:
    if not (
        isinstance(request.user, User)
        and request.user.is_active
        and request.user.is_superuser
    ):
        raise PermissionDenied
    return request.user


def _context(site: AdminSite, request: HttpRequest, title: str) -> dict[str, Any]:
    return {
        **site.each_context(request),
        "title": title,
        "TaskResultStatus": TaskResultStatus,
    }


def _redirect_receipt(receipt: OperationReceipt) -> HttpResponse:
    query = (
        urlencode({"group": receipt.group_id})
        if receipt.group_id
        else urlencode([("task", task_id) for task_id in receipt.task_ids])
    )
    return redirect(f"{reverse('admin:operations_receipt')}?{query}")


def _confirmation(
    site: AdminSite, request: HttpRequest, project: Project
) -> TemplateResponse:
    return TemplateResponse(
        request,
        "admin/background_operations/confirm.html",
        {
            **_context(site, request, "Confirm Git history rebuild"),
            "project": project,
            "skip_geojson": project.exclude_geojson or not project.supports_geojson,
            "confirmation": signing.dumps(
                {"project_id": str(project.pk)}, salt=CONFIRMATION_SALT
            ),
        },
    )


def operations(site: AdminSite, request: HttpRequest) -> HttpResponse:
    requester = _operator(request)
    if request.method not in {"GET", "POST"}:
        return HttpResponseNotAllowed(["GET", "POST"])
    operation = request.POST.get("operation") if request.method == "POST" else None
    history = ProjectOperationForm(
        request.POST if operation == "history" else None, prefix="history"
    )
    project = ProjectGeoJSONForm(
        request.POST if operation == "project" else None, prefix="project"
    )
    all_projects = AllGeoJSONForm(
        request.POST if operation == "all" else None, prefix="all"
    )
    forms = {"history": history, "project": project, "all": all_projects}
    if request.method == "POST":
        if operation not in forms:
            raise Http404
        form = forms[operation]
        if form.is_valid():
            if operation == "history":
                return _confirmation(site, request, form.cleaned_data["project_id"])
            selected = form.cleaned_data.get("project_id")
            return _redirect_receipt(
                schedule_operation(
                    operation,
                    requester=requester,
                    project_id=selected.pk if selected is not None else None,
                    force=form.cleaned_data["force"],
                )
            )
    return TemplateResponse(
        request,
        "admin/background_operations/operations.html",
        {
            **_context(site, request, "Operations"),
            "history_form": history,
            "project_form": project,
            "all_form": all_projects,
            "eligible_count": eligible_projects().count(),
        },
    )


def confirm_operation(site: AdminSite, request: HttpRequest) -> HttpResponse:
    requester = _operator(request)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        data = signing.loads(
            request.POST.get("confirmation", ""),
            salt=CONFIRMATION_SALT,
            max_age=3600,
        )
        project_id = UUID(data["project_id"])
    except (signing.BadSignature, KeyError, TypeError, ValueError) as error:
        raise PermissionDenied(
            "The confirmation expired or is invalid. Start again."
        ) from error
    project = get_object_or_404(Project, pk=project_id)
    return _redirect_receipt(
        schedule_operation("history", requester=requester, project_id=project.pk)
    )


def _json_object(value: str | None) -> dict[str, Any]:
    try:
        decoded = json.loads(value or "{}")
    except ValueError, TypeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def operation_receipt(site: AdminSite, request: HttpRequest) -> HttpResponse:
    _operator(request)
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    try:
        group_id = request.GET.get("group")
        task_ids = (
            receipt_task_ids(group_id)
            if group_id
            else [str(UUID(value)) for value in request.GET.getlist("task")]
        )
    except ValueError as error:
        raise Http404 from error
    results = list(
        TaskResult.objects.filter(task_id__in=task_ids).order_by(
            "date_created", "task_id"
        )
    )
    if (not task_ids and not group_id) or len(results) != len(set(task_ids)):
        raise Http404
    rows = []
    for result in results:
        if result.task_name not in TASK_NAMES.values():
            raise Http404
        try:
            parameters = get_operation_parameters(result)
        except ValueError:
            # Celery can fail before entering our execution guard (for example,
            # an old worker rejecting the new task signature). Its backend may
            # then replace operation metadata; the failure must stay inspectable.
            parameters = None
        metadata = _json_object(result.meta)
        details = _json_object(result.result)
        summary = metadata.get("summary")
        if isinstance(summary, dict):
            details = summary
        try:
            deadline = parse_datetime(metadata.get("deadline", ""))
        except ValueError, TypeError:
            deadline = None
        completion_unconfirmed = (
            result.status
            not in {
                TaskResultStatus.SUCCESS,
                TaskResultStatus.FAILURE,
                TaskResultStatus.REVOKED,
            }
            and metadata.get("publication") != "unattempted"
            and deadline is not None
            and timezone.is_aware(deadline)
            and deadline <= timezone.now()
        )
        if completion_unconfirmed:
            display_status = "COMPLETION UNCONFIRMED"
        elif result.status == TaskResultStatus.PENDING:
            display_status = {
                "confirmed": "QUEUED",
                "ambiguous": "SUBMISSION UNCONFIRMED",
                "unattempted": "NOT SUBMITTED",
            }.get(str(metadata.get("publication")), "SUBMISSION UNCONFIRMED")
        else:
            status_labels: dict[str, str] = {
                TaskResultStatus.STARTED: "IN PROGRESS",
                TaskResultStatus.SUCCESS: "SUCCEEDED",
                TaskResultStatus.FAILURE: "FAILED",
                TaskResultStatus.REVOKED: TaskResultStatus.REVOKED.value,
            }
            display_status = status_labels.get(result.status, result.status)
        rows.append(
            {
                "result": result,
                "parameters": parameters,
                "metadata": metadata,
                "details": details if isinstance(details, dict) else {},
                "completion_unconfirmed": completion_unconfirmed,
                "display_status": display_status,
            }
        )
    return TemplateResponse(
        request,
        "admin/background_operations/receipt.html",
        {**_context(site, request, "Operation receipts"), "rows": rows},
    )


def rerun_operation(
    site: AdminSite, request: HttpRequest, task_id: UUID
) -> HttpResponse:
    requester = _operator(request)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    result = get_object_or_404(TaskResult, task_id=str(task_id))
    try:
        parameters = get_operation_parameters(result)
    except ValueError as error:
        raise Http404 from error
    if parameters["operation"] == "history":
        project = get_object_or_404(Project, pk=parameters["project_id"])
        return _confirmation(site, request, project)
    try:
        receipt = schedule_operation(requester=requester, **parameters)
    except Project.DoesNotExist, ValueError:
        messages.error(
            request,
            "This project is unavailable or no longer eligible for GeoJSON generation.",
        )
        return redirect(reverse("admin:operations"))
    return _redirect_receipt(receipt)
