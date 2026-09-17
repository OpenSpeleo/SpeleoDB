"""Exercise export authorization and lifecycle through real API/database rows."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from urllib.parse import parse_qs
from urllib.parse import urlsplit

from django.contrib.admin.models import LogEntry
from django.test import override_settings
from django.urls import resolve
from django.urls import reverse
from django.utils import timezone
from django_celery_results.models import GroupResult
from django_celery_results.models import TaskResult
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.background_jobs.models import BackgroundJob
from speleodb.background_jobs.models import JobArtifact
from speleodb.background_jobs.models import JobAttempt
from speleodb.background_jobs.models import JobState
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.users.models import User


class TestUserExports(BaseAPITestCase):
    def _job(
        self, state: str = JobState.QUEUED, *, requester: User | None = None
    ) -> BackgroundJob:
        return BackgroundJob.objects.create(
            requester=requester or self.user, state=state
        )

    def _artifact(self, job: BackgroundJob, *, expired: bool = False) -> JobArtifact:
        attempt: JobAttempt = JobAttempt.objects.create(
            job=job, number=1, state=job.state
        )
        now = timezone.now()
        return JobArtifact.objects.create(
            job=job,
            attempt=attempt,
            object_key=f"exports/{self.user.pk}/{job.pk}/{attempt.pk}.zip",
            filename="speleodb-export.zip",
            size_bytes=1234,
            sha256="a" * 64,
            ready_at=now - timedelta(hours=24),
            expires_at=now - timedelta(seconds=1)
            if expired
            else now + timedelta(hours=1),
        )

    def test_routes_and_login_requirement(self) -> None:
        job: BackgroundJob = self._job()
        for name in ("user-export-detail", "user-export-retry", "user-export-download"):
            url: str = reverse(f"api:v2:{name}", kwargs={"id": job.pk})
            assert resolve(url).view_name == f"api:v2:{name}"
        response = self.client.get(reverse("api:v2:user-exports"))
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_request_is_durable_and_duplicate_requests_share_one_attempt(self) -> None:
        assert self.user.is_active
        assert not self.user.is_staff
        url: str = reverse("api:v2:user-exports")
        other: User = UserFactory.create()
        first = self.client.post(
            url, {"requester": other.pk}, headers={"authorization": self.auth}
        )
        second = self.client.post(url, headers={"authorization": self.auth})
        assert first.status_code == status.HTTP_202_ACCEPTED
        assert second.status_code == status.HTTP_202_ACCEPTED
        assert first.data["id"] == second.data["id"]
        job: BackgroundJob = BackgroundJob.objects.get(pk=first.data["id"])
        assert job.requester == self.user
        assert job.attempts.count() == 1
        assert first.data["artifact"] is None
        assert first.data["download_url"] is None

    def test_owner_history_is_paginated_and_excludes_other_users_even_for_staff(
        self,
    ) -> None:
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        for _ in range(21):
            self._job(JobState.FAILED)
        self._job(JobState.READY, requester=UserFactory.create())
        response = self.client.get(
            reverse("api:v2:user-exports"), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 21  # noqa: PLR2004
        assert len(response.data["results"]) == 20  # noqa: PLR2004
        assert response.data["next"] is not None

    def test_history_excludes_expired_and_deleted_archives_before_pagination(
        self,
    ) -> None:
        visible: list[BackgroundJob] = [
            self._job(JobState.READY),
            self._job(JobState.PARTIAL),
            self._job(JobState.FAILED),
            self._job(JobState.QUEUED),
        ]
        for job in visible[:2]:
            self._artifact(job)
        for _ in range(21):
            self._artifact(self._job(JobState.READY), expired=True)
        deleted: JobArtifact = self._artifact(self._job(JobState.PARTIAL))
        deleted.deleted_at = timezone.now()
        deleted.save(update_fields=["deleted_at"])

        response = self.client.get(
            reverse("api:v2:user-exports"), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == len(visible)
        assert response.data["next"] is None
        assert {entry["id"] for entry in response.data["results"]} == {
            str(job.pk) for job in visible
        }
        assert JobArtifact.objects.filter(deleted_at__isnull=False).exists()

    def test_history_keeps_active_retry_with_an_older_expired_artifact(self) -> None:
        job: BackgroundJob = self._job(JobState.RETRY_WAIT)
        self._artifact(job, expired=True)
        response = self.client.get(
            reverse("api:v2:user-exports"), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_200_OK
        assert [entry["id"] for entry in response.data["results"]] == [str(job.pk)]

    def test_other_users_cannot_inspect_retry_or_download(self) -> None:
        job: BackgroundJob = self._job(JobState.FAILED, requester=UserFactory.create())
        for name in ("user-export-detail", "user-export-download"):
            response = self.client.get(
                reverse(f"api:v2:{name}", kwargs={"id": job.pk}),
                headers={"authorization": self.auth},
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND
        response = self.client.post(
            reverse("api:v2:user-export-retry", kwargs={"id": job.pk}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_inactive_account_cannot_read_create_retry_or_download(self) -> None:
        job: BackgroundJob = self._job(JobState.FAILED)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        for name in ("user-export-detail", "user-export-download"):
            response = self.client.get(
                reverse(f"api:v2:{name}", kwargs={"id": job.pk}),
                headers={"authorization": self.auth},
            )
            assert response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            )
        list_url: str = reverse("api:v2:user-exports")
        response = self.client.get(list_url, headers={"authorization": self.auth})
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
        response = self.client.post(list_url, headers={"authorization": self.auth})
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
        response = self.client.post(
            reverse("api:v2:user-export-retry", kwargs={"id": job.pk}),
            headers={"authorization": self.auth},
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
        assert job.attempts.count() == 0

    def test_retry_retains_attempt_history_and_reports_an_active_conflict(self) -> None:
        failed: BackgroundJob = self._job(JobState.FAILED)
        JobAttempt.objects.create(
            job=failed, number=1, state=JobState.FAILED, error="Source unavailable"
        )
        active: BackgroundJob = self._job()
        url: str = reverse("api:v2:user-export-retry", kwargs={"id": failed.pk})
        conflict = self.client.post(url, headers={"authorization": self.auth})
        assert conflict.status_code == status.HTTP_409_CONFLICT
        assert conflict.data["active_job_id"] == str(active.pk)
        active.state = JobState.FAILED
        active.save(update_fields=["state"])
        response = self.client.post(url, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_202_ACCEPTED
        failed.refresh_from_db()
        assert failed.state == JobState.QUEUED
        assert failed.attempts.count() == 2  # noqa: PLR2004
        assert failed.attempts.get(number=1).error == "Source unavailable"

    def test_partial_export_exposes_omissions_and_safe_attachment_metadata(
        self,
    ) -> None:
        job: BackgroundJob = self._job(JobState.PARTIAL)
        job.summary = {
            "omissions": [
                {
                    "category": "projects",
                    "name": "Unavailable cave",
                    "reason": "Source unavailable",
                }
            ]
        }
        job.save(update_fields=["summary"])
        artifact: JobArtifact = self._artifact(job)
        response = self.client.get(
            reverse("api:v2:user-export-detail", kwargs={"id": job.pk}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["summary"]["omissions"][0]["name"] == "Unavailable cave"
        assert response.data["artifact"]["filename"] == artifact.filename
        assert response.data["download_url"] == reverse(
            "api:v2:user-export-download", kwargs={"id": job.pk}
        )
        assert "object_key" not in response.data["artifact"]
        assert "notification_error" not in response.data

    def test_expiry_removes_download_and_returns_gone(self) -> None:
        job: BackgroundJob = self._job(JobState.READY)
        self._artifact(job, expired=True)
        detail = self.client.get(
            reverse("api:v2:user-export-detail", kwargs={"id": job.pk}),
            headers={"authorization": self.auth},
        )
        assert detail.data["expired"] is True
        assert detail.data["download_url"] is None
        response = self.client.get(
            reverse("api:v2:user-export-download", kwargs={"id": job.pk}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_410_GONE

    def test_download_signing_is_short_lived_and_response_is_not_cacheable(
        self,
    ) -> None:
        job: BackgroundJob = self._job(JobState.READY)
        artifact: JobArtifact = self._artifact(job)
        response = self.client.get(
            reverse("api:v2:user-export-download", kwargs={"id": job.pk}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_302_FOUND
        assert response["Cache-Control"] == "private, no-store"
        assert response["Referrer-Policy"] == "no-referrer"
        parameters: dict[str, list[str]] = parse_qs(
            urlsplit(response["Location"]).query
        )
        assert 0 < int(parameters["X-Amz-Expires"][0]) <= 300  # noqa: PLR2004
        assert all(name.startswith("X-Amz-") for name in parameters)
        assert urlsplit(response["Location"]).path.endswith(f"/{artifact.object_key}")

    def test_settings_page_uses_registered_controller_and_both_navigation_links(
        self,
    ) -> None:
        self.client.force_login(self.user)
        url: str = reverse("private:user_exports")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        html: str = response.content.decode()
        assert 'data-speleodb-controller="user-exports"' in html
        assert html.count(f'href="{url}"') == 2  # noqa: PLR2004
        assert 'id="export-create"' in html
        assert 'id="export-selected"' not in html
        assert html.count('id="export-history"') == 1
        assert "Recent exports" not in html
        assert "24 hours" in html
        assert "6 datasets" in html
        assert "GIS geometries" in html
        assert "Your accessible lines and polygons as GeoJSON" in html
        assert 'name="csrfmiddlewaretoken"' in html

    def test_admin_staff_can_inspect_and_retry_but_cannot_download_others_exports(
        self,
    ) -> None:
        staff: User = UserFactory.create(is_staff=True)
        ready: BackgroundJob = self._job(JobState.READY)
        self._artifact(ready)
        failed: BackgroundJob = self._job(JobState.FAILED)
        self.client.force_login(staff)
        detail_url: str = reverse(
            "admin:background_jobs_backgroundjob_change", args=[ready.pk]
        )
        detail = self.client.get(detail_url)
        assert detail.status_code == status.HTTP_200_OK
        assert (
            f"task_id__exact={ready.attempts.get().task_id}" in detail.content.decode()
        )
        download_url: str = reverse(
            "api:v2:user-export-download", kwargs={"id": ready.pk}
        )
        assert f'href="{download_url}"' not in detail.content.decode()
        assert self.client.get(download_url).status_code == status.HTTP_404_NOT_FOUND
        response = self.client.post(
            reverse("admin:background_jobs_backgroundjob_changelist"),
            {"action": "retry_failed", "_selected_action": [str(failed.pk)]},
        )
        assert response.status_code == status.HTTP_302_FOUND
        failed.refresh_from_db()
        assert failed.state == JobState.QUEUED
        assert LogEntry.objects.filter(
            user=staff,
            object_id=str(failed.pk),
            change_message__contains="new export attempt",
        ).exists()

    def test_admin_superuser_has_authorized_download_and_kanchi_root_link(self) -> None:
        superuser: User = UserFactory.create(is_staff=True, is_superuser=True)
        ready: BackgroundJob = self._job(JobState.READY)
        self._artifact(ready)
        self.client.force_login(superuser)
        with override_settings(KANCHI_URL="https://kanchi.example.test"):
            response = self.client.get(
                reverse("admin:background_jobs_backgroundjob_change", args=[ready.pk])
            )
        assert response.status_code == status.HTTP_200_OK
        download_url: str = reverse(
            "api:v2:user-export-download", kwargs={"id": ready.pk}
        )
        assert f'href="{download_url}"' in response.content.decode()
        assert 'href="https://kanchi.example.test"' in response.content.decode()
        assert self.client.get(download_url).status_code == status.HTTP_302_FOUND

    def test_admin_notification_retry_handles_expired_archives(self) -> None:
        staff: User = UserFactory.create(is_staff=True)
        job: BackgroundJob = self._job(JobState.READY)
        artifact: JobArtifact = self._artifact(job, expired=True)
        job.notification_state = "failed"
        job.save(update_fields=["notification_state"])
        self.client.force_login(staff)
        response = self.client.post(
            reverse("admin:background_jobs_backgroundjob_changelist"),
            {"action": "retry_notifications", "_selected_action": [str(job.pk)]},
            follow=True,
        )
        assert response.status_code == status.HTTP_200_OK
        assert "This archive has expired" in response.content.decode()
        job.refresh_from_db()
        assert job.notification_state == "failed"
        assert job.artifact == artifact
        assert job.attempts.count() == 1

    def test_technical_result_admin_is_read_only_for_staff_and_superusers(self) -> None:
        task: TaskResult = TaskResult.objects.create(
            task_id="11111111-1111-4111-8111-111111111111",
            task_name="speleodb.background_jobs.tasks.generate_export",
            status="FAILURE",
            content_type="application/json",
            content_encoding="utf-8",
            result='{"error": "Source unavailable"}',
        )
        group: GroupResult = GroupResult.objects.create(
            group_id="22222222-2222-4222-8222-222222222222",
            content_type="application/json",
            content_encoding="utf-8",
            result="[]",
        )
        for is_superuser in (False, True):
            operator: User = UserFactory.create(
                is_staff=True, is_superuser=is_superuser
            )
            self.client.force_login(operator)
            for model_name, obj in (("taskresult", task), ("groupresult", group)):
                prefix: str = f"admin:django_celery_results_{model_name}"
                change_url: str = reverse(f"{prefix}_change", args=[obj.pk])
                response = self.client.get(change_url)
                assert response.status_code == status.HTTP_200_OK
                assert 'name="_save"' not in response.content.decode()
                assert (
                    self.client.post(change_url, {"status": "SUCCESS"}).status_code
                    == status.HTTP_403_FORBIDDEN
                )
                assert (
                    self.client.get(reverse(f"{prefix}_add")).status_code
                    == status.HTTP_403_FORBIDDEN
                )
                assert (
                    self.client.post(
                        reverse(f"{prefix}_delete", args=[obj.pk]), {"post": "yes"}
                    ).status_code
                    == status.HTTP_403_FORBIDDEN
                )
            task.refresh_from_db()
            assert task.status == "FAILURE"
            assert GroupResult.objects.filter(pk=group.pk).exists()
