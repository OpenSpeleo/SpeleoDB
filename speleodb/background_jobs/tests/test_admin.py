"""Operations forms enforce superuser access before scheduling operations."""

from __future__ import annotations

import json
from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from django.contrib import admin
from django.core import signing
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.background_jobs.operation_views import CONFIRMATION_SALT
from speleodb.background_jobs.operations import TASK_NAMES
from speleodb.common.enums import ProjectType
from speleodb.common.enums import TaskResultStatus
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from kombu.simple import SimpleQueue
    from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks

    from speleodb.surveys.models import Project
    from speleodb.users.models import User


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
def test_operations_navigation_and_force_defaults(admin_client: Client) -> None:
    response = admin_client.get(reverse("admin:operations"))
    assert response.status_code == HTTPStatus.OK
    content = response.content.decode()
    assert "Rebuild Git history" in content
    assert "Generate missing GeoJSONs" in content
    assert "checked" not in content
    assert "all-project_id" not in content
    groups = admin.site.get_app_list(response.wsgi_request)
    group = next(group for group in groups if group["name"] == "Background operations")
    assert [model["name"] for model in group["models"]] == [
        "Operations",
        "Export jobs",
        "Task results",
        "Group results",
    ]
    exports = admin_client.get(
        reverse("admin:background_jobs_backgroundjob_changelist")
    )
    assert 'href="' + reverse("admin:operations") + '"' in exports.content.decode()
    assert "Rebuild all GeoJSONs" not in exports.content.decode()


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
@pytest.mark.parametrize(
    ("is_staff", "is_superuser", "is_active", "expected"),
    [
        (False, False, True, HTTPStatus.FOUND),
        (True, False, True, HTTPStatus.FORBIDDEN),
        (True, True, False, HTTPStatus.FOUND),
    ],
)
def test_custom_routes_reject_other_users(
    client: Client, is_staff: bool, is_superuser: bool, is_active: bool, expected: int
) -> None:
    user = UserFactory.create(
        is_staff=is_staff, is_superuser=is_superuser, is_active=is_active
    )
    client.force_login(user)
    routes = [
        ("operations", {}),
        ("operations_confirm", {}),
        ("operations_receipt", {}),
        ("operations_rerun", {"task_id": uuid4()}),
    ]
    for name, kwargs in routes:
        assert (
            client.post(reverse(f"admin:{name}", kwargs=kwargs)).status_code == expected
        )
    assert not TaskResult.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
def test_anonymous_routes_require_login(client: Client) -> None:
    assert client.post(reverse("admin:operations")).status_code == HTTPStatus.FOUND


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
def test_mutation_routes_require_post(admin_client: Client) -> None:
    for name, kwargs in [
        ("operations_confirm", {}),
        ("operations_rerun", {"task_id": uuid4()}),
    ]:
        response = admin_client.get(reverse(f"admin:{name}", kwargs=kwargs))
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert response.headers["Allow"] == "POST"


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
def test_uuid_validation_and_project_resolution(
    admin_client: Client, project: Project
) -> None:
    response = admin_client.post(
        reverse("admin:operations"),
        {"operation": "history", "history-project_id": "invalid"},
    )
    assert "Select a valid choice" in response.content.decode()
    response = admin_client.post(
        reverse("admin:operations"),
        {"operation": "history", "history-project_id": str(uuid4())},
    )
    assert "Select a valid choice" in response.content.decode()
    response = admin_client.post(
        reverse("admin:operations"),
        {"operation": "history", "history-project_id": str(project.pk)},
    )
    assert project.name in response.content.decode()
    assert str(project.pk) in response.content.decode()
    assert "retired and orphaned" in response.content.decode()
    assert not TaskResult.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
def test_history_confirmation_and_rerun_are_destructive(
    admin_client: Client,
    admin_user: User,
    project: Project,
    operation_queue: SimpleQueue,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    project.exclude_geojson = True
    project.save()
    response = admin_client.post(
        reverse("admin:operations"),
        {"operation": "history", "history-project_id": str(project.pk)},
    )
    assert "GeoJSON regeneration will be skipped" in response.content.decode()
    assert response.context_data is not None
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(
            reverse("admin:operations_confirm"),
            {"confirmation": response.context_data["confirmation"]},
        )
    result = TaskResult.objects.get()
    assert response.status_code == HTTPStatus.FOUND
    assert result.task_id in response.headers["Location"]
    assert result.task_name == TASK_NAMES["history"]
    metadata = json.loads(result.meta)
    assert metadata["requester_id"] == str(admin_user.pk)
    assert metadata["project_id"] == str(project.pk)
    message = operation_queue.get(block=False)
    assert message.headers["id"] == result.task_id
    message.ack()
    response = admin_client.post(
        reverse("admin:operations_rerun", kwargs={"task_id": result.task_id})
    )
    assert response.status_code == HTTPStatus.OK
    assert "Confirm destructive history rebuild" in response.content.decode()
    assert TaskResult.objects.count() == 1
    assert operation_queue.qsize() == 0
    assert (
        admin_client.post(
            reverse("admin:operations_confirm"), {"confirmation": "bad"}
        ).status_code
        == HTTPStatus.FORBIDDEN
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
def test_project_eligibility_and_force(
    admin_client: Client,
    admin_user: User,
    project: Project,
    operation_queue: SimpleQueue,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    project.type = ProjectType.COMPASS
    project.exclude_geojson = True
    project.save()
    data = {"operation": "project", "project-project_id": str(project.pk)}
    response = admin_client.post(reverse("admin:operations"), data)
    assert "excluded" in response.content.decode()
    assert not TaskResult.objects.exists()
    project.exclude_geojson = False
    project.type = ProjectType.THERION
    project.save()
    response = admin_client.post(reverse("admin:operations"), data)
    assert "unsupported" in response.content.decode()
    assert not TaskResult.objects.exists()
    project.type = ProjectType.COMPASS
    project.save()
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(reverse("admin:operations"), data)
    first = TaskResult.objects.get()
    first_metadata = json.loads(first.meta)
    assert first_metadata["force"] is False
    assert first_metadata["project_id"] == str(project.pk)
    assert first_metadata["requester_id"] == str(admin_user.pk)
    data["project-force"] = "on"
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(reverse("admin:operations"), data)
    second = TaskResult.objects.exclude(pk=first.pk).get()
    assert json.loads(second.meta)["force"] is True
    assert operation_queue.qsize() == TaskResult.objects.count()


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
def test_global_count_and_scheduling(
    admin_client: Client,
    project: Project,
    operation_queue: SimpleQueue,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    project.type = ProjectType.COMPASS
    project.exclude_geojson = False
    project.save()
    response = admin_client.get(reverse("admin:operations"))
    assert response.context_data is not None
    assert response.context_data["eligible_count"] == 1
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(reverse("admin:operations"), {"operation": "all"})
    assert "group=" in response.headers["Location"]
    result = TaskResult.objects.get()
    assert json.loads(result.meta)["project_id"] == str(project.pk)
    assert json.loads(result.meta)["force"] is False
    assert operation_queue.qsize() == 1


def _task(project: Project, operation: str = "project") -> TaskResult:
    return TaskResult.objects.create(
        task_id=str(uuid4()),
        task_name=TASK_NAMES[operation],
        status=TaskResultStatus.PENDING,
        meta=json.dumps(
            {
                "operation": operation,
                "project_id": str(project.pk),
                "project_name": project.name,
                "force": True,
                "stage": "queued",
                "publication": "ambiguous",
                "deadline": (timezone.now() - timedelta(seconds=1)).isoformat(),
            }
        ),
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
def test_receipt_honest_status_and_supported_rerun(
    admin_client: Client,
    admin_user: User,
    project: Project,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    result = _task(project)
    response = admin_client.get(
        reverse("admin:operations_receipt"), {"task": result.task_id}
    )
    content = response.content.decode()
    assert "Completion unconfirmed" in content
    assert "Delivery ambiguous" in content
    assert "Force recompute: on" in content
    assert (
        reverse("admin:django_celery_results_taskresult_change", args=[result.pk])
        in content
    )
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(
            reverse("admin:operations_rerun", kwargs={"task_id": result.task_id})
        )
    assert response.status_code == HTTPStatus.FOUND
    repeated = TaskResult.objects.exclude(pk=result.pk).get()
    assert repeated.task_id != result.task_id
    assert json.loads(repeated.meta)["force"] is True
    assert json.loads(repeated.meta)["requester_id"] == str(admin_user.pk)
    metadata = json.loads(result.meta)
    metadata["summary"] = {
        "processed": 2,
        "generated": 1,
        "existing": 0,
        "skipped": 0,
        "failed": 1,
    }
    metadata["project_name"] = "Invalid <survey>"
    result.meta = json.dumps(metadata)
    result.status = TaskResultStatus.FAILURE
    result.result = json.dumps({"exc_message": "private secret traceback"})
    result.save()
    response = admin_client.get(
        reverse("admin:operations_receipt"), {"task": result.task_id}
    )
    content = response.content.decode()
    assert "generated: 1" in content
    assert "failed: 1" in content
    assert "Invalid &lt;survey&gt;" in content
    assert "private secret traceback" not in content
    assert "Completion unconfirmed" not in content
    task_response = admin_client.get(
        reverse("admin:django_celery_results_taskresult_change", args=[result.pk])
    )
    assert task_response.status_code == HTTPStatus.OK
    assert "Background operations" in task_response.content.decode()
    result.task_name = "unrelated.task"
    result.save()
    assert (
        admin_client.get(
            reverse("admin:operations_receipt"), {"task": result.task_id}
        ).status_code
        == HTTPStatus.NOT_FOUND
    )
    assert (
        admin_client.post(
            reverse("admin:operations_rerun", kwargs={"task_id": result.task_id})
        ).status_code
        == HTTPStatus.NOT_FOUND
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
def test_csrf_on_operations_and_confirmation(
    admin_user: User, project: Project
) -> None:
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    assert (
        client.post(reverse("admin:operations"), {"operation": "all"}).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert (
        client.post(
            reverse("admin:operations_confirm"),
            {
                "confirmation": signing.dumps(
                    {"project_id": str(project.pk)}, salt=CONFIRMATION_SALT
                )
            },
        ).status_code
        == HTTPStatus.FORBIDDEN
    )
    client.get(reverse("admin:operations"))
    response = client.post(
        reverse("admin:operations"),
        {
            "operation": "history",
            "history-project_id": str(project.pk),
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert not TaskResult.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
def test_export_staff_permissions_remain(staff_client: Client) -> None:
    response = staff_client.get(
        reverse("admin:background_jobs_backgroundjob_changelist")
    )
    assert response.status_code == HTTPStatus.OK
    assert "Open Operations" not in response.content.decode()
    assert (
        staff_client.get(
            reverse("admin:django_celery_results_taskresult_changelist")
        ).status_code
        == HTTPStatus.OK
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
@pytest.mark.parametrize("metadata", ['{"children": []}', "null", "invalid"])
def test_preexecution_failure_receipt_survives_lost_parameters(
    admin_client: Client, metadata: str
) -> None:
    result = TaskResult.objects.create(
        task_id=str(uuid4()),
        task_name=TASK_NAMES["project"],
        status=TaskResultStatus.FAILURE,
        meta=metadata,
        result=json.dumps({"exc_message": "private error details"}),
    )
    response = admin_client.get(
        reverse("admin:operations_receipt"), {"task": result.task_id}
    )
    assert response.status_code == HTTPStatus.OK
    content = response.content.decode()
    assert "Status: FAILED" in content
    assert "This task failed. Execution details are unavailable" in content
    assert "Operation parameters are unavailable" in content
    assert "Submission details are unavailable" in content
    assert "Publication unattempted" not in content
    assert "private error details" not in content
    assert ">Run again<" not in content
    assert reverse("admin:operations") in content
    assert (
        reverse("admin:django_celery_results_taskresult_change", args=[result.pk])
        in content
    )
    response = admin_client.post(
        reverse("admin:operations_rerun", kwargs={"task_id": result.task_id})
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert TaskResult.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
@pytest.mark.parametrize(
    ("status", "publication", "display"),
    [
        (TaskResultStatus.PENDING, "confirmed", "QUEUED"),
        (TaskResultStatus.STARTED, "confirmed", "IN PROGRESS"),
        (TaskResultStatus.SUCCESS, "confirmed", "SUCCEEDED"),
        (TaskResultStatus.FAILURE, "confirmed", "FAILED"),
        (TaskResultStatus.PENDING, "ambiguous", "SUBMISSION UNCONFIRMED"),
        (TaskResultStatus.PENDING, "unattempted", "NOT SUBMITTED"),
    ],
)
def test_receipt_displays_operator_status(
    admin_client: Client, project: Project, status: str, publication: str, display: str
) -> None:
    result = _task(project)
    metadata = json.loads(result.meta)
    metadata.update(
        publication=publication,
        deadline=(timezone.now() + timedelta(hours=1)).isoformat(),
    )
    result.meta = json.dumps(metadata)
    result.status = status
    result.save()
    response = admin_client.get(
        reverse("admin:operations_receipt"), {"task": result.task_id}
    )
    assert f"Status: {display}" in response.content.decode()


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
def test_project_selector_searches_names_and_identifiers(
    admin_client: Client, project: Project
) -> None:
    response = admin_client.get(reverse("admin:operations"))
    content = response.content.decode()
    assert 'class="admin-autocomplete"' in content
    assert "Type a project name or UUID" in content
    assert "admin/js/autocomplete.js" in content
    for term in [project.name, str(project.pk)]:
        response = admin_client.get(
            reverse("admin:autocomplete"),
            {
                "app_label": "surveys",
                "model_name": "projectcommit",
                "field_name": "project",
                "term": term,
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json()["results"] == [
            {"id": str(project.pk), "text": f"{project.name} ({project.pk})"}
        ]


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
@pytest.mark.parametrize("change", ["deleted", "excluded", "unsupported"])
def test_rerun_handles_project_no_longer_eligible(
    admin_client: Client,
    project: Project,
    change: str,
) -> None:
    result = _task(project, "project")
    if change == "deleted":
        project.delete()
    elif change == "excluded":
        project.exclude_geojson = True
        project.save(update_fields=["exclude_geojson"])
    else:
        project.type = ProjectType.OTHER
        project.save(update_fields=["type"])
    response = admin_client.post(
        reverse("admin:operations_rerun", kwargs={"task_id": result.task_id}),
        follow=True,
    )
    assert response.status_code == HTTPStatus.OK
    assert "no longer eligible" in response.content.decode()
    assert TaskResult.objects.count() == 1
