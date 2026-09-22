"""One-shot global maintenance dispatch through Django admin."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from django.contrib import messages
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django_celery_beat.models import PeriodicTask
from kombu.exceptions import OperationalError
from rest_framework import status

if TYPE_CHECKING:
    from speleodb.users.models import User


@pytest.mark.django_db
def test_superuser_dispatches_once_without_a_schedule(admin_client: Client) -> None:
    url = reverse("admin:background_jobs_backgroundjob_rebuild_geojson")
    list_url = reverse("admin:background_jobs_backgroundjob_changelist")
    schedules = list(PeriodicTask.objects.values())
    response = admin_client.get(list_url)
    assert response.status_code == status.HTTP_200_OK
    assert f'action="{url}"' in response.content.decode()
    assert "Rebuild all GeoJSONs" in response.content.decode()
    assert "admin-background-jobs" in response.content.decode()

    with patch(
        "speleodb.background_jobs.admin.refresh_all_projects_geojson.delay"
    ) as delay:
        delay.return_value.id = "test-rebuild-task"
        response = admin_client.post(url, follow=True)
        assert response.redirect_chain == [(list_url, status.HTTP_302_FOUND)]
        notices = list(get_messages(response.wsgi_request))
        assert len(notices) == 1
        assert notices[0].level == messages.SUCCESS
        assert "test-rebuild-task" in str(notices[0])
        admin_client.get(list_url)
        delay.assert_called_once_with()

    assert list(PeriodicTask.objects.values()) == schedules


@pytest.mark.django_db
def test_projects_list_has_no_global_maintenance_button(admin_client: Client) -> None:
    response = admin_client.get(reverse("admin:surveys_project_changelist"))
    assert response.status_code == status.HTTP_200_OK
    assert "Rebuild all GeoJSONs" not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "head", "put", "delete"])
def test_dispatch_requires_post(admin_client: Client, method: str) -> None:
    with patch(
        "speleodb.background_jobs.admin.refresh_all_projects_geojson.delay"
    ) as delay:
        response = getattr(admin_client, method)(
            reverse("admin:background_jobs_backgroundjob_rebuild_geojson")
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert response.headers["Allow"] == "POST"
        delay.assert_not_called()


@pytest.mark.django_db
def test_staff_cannot_dispatch_global_rebuild(staff_client: Client) -> None:
    response = staff_client.get(
        reverse("admin:background_jobs_backgroundjob_changelist")
    )
    assert response.status_code == status.HTTP_200_OK
    assert "Rebuild all GeoJSONs" not in response.content.decode()
    with patch(
        "speleodb.background_jobs.admin.refresh_all_projects_geojson.delay"
    ) as delay:
        response = staff_client.post(
            reverse("admin:background_jobs_backgroundjob_rebuild_geojson")
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        delay.assert_not_called()


@pytest.mark.django_db
def test_anonymous_cannot_dispatch_global_rebuild(client: Client) -> None:
    with patch(
        "speleodb.background_jobs.admin.refresh_all_projects_geojson.delay"
    ) as delay:
        response = client.post(
            reverse("admin:background_jobs_backgroundjob_rebuild_geojson")
        )
        assert response.status_code == status.HTTP_302_FOUND
        delay.assert_not_called()


@pytest.mark.django_db
def test_dispatch_requires_csrf_token(admin_user: User) -> None:
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    url = reverse("admin:background_jobs_backgroundjob_rebuild_geojson")
    with patch(
        "speleodb.background_jobs.admin.refresh_all_projects_geojson.delay"
    ) as delay:
        response = client.post(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        delay.assert_not_called()
        client.get(reverse("admin:background_jobs_backgroundjob_changelist"))
        response = client.post(
            url, {"csrfmiddlewaretoken": client.cookies["csrftoken"].value}
        )
        assert response.status_code == status.HTTP_302_FOUND
        delay.assert_called_once_with()


@pytest.mark.django_db
def test_broker_failure_does_not_report_success(admin_client: Client) -> None:
    with patch(
        "speleodb.background_jobs.admin.refresh_all_projects_geojson.delay",
        side_effect=OperationalError("broker unavailable"),
    ) as delay:
        response = admin_client.post(
            reverse("admin:background_jobs_backgroundjob_rebuild_geojson"), follow=True
        )
    delay.assert_called_once_with()
    notices = list(get_messages(response.wsgi_request))
    assert len(notices) == 1
    assert notices[0].level == messages.ERROR
    assert "Could not confirm" in str(notices[0])
    assert "Task ID:" not in str(notices[0])
