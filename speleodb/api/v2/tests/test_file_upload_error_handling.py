# -*- coding: utf-8 -*-

"""Upload failures exercised through real GitLab, Git, SQL, and Sentry SDK paths."""

from __future__ import annotations

import pathlib
import shutil
import tempfile
import uuid
from functools import partial
from typing import TYPE_CHECKING
from typing import cast

import git
import gitlab.exceptions
import pytest
import sentry_sdk
from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db import transaction
from django.db.utils import IntegrityError
from django.http import Http404
from django.test import RequestFactory
from django.test import TransactionTestCase
from django.test import override_settings
from django.urls import reverse
from django.views.static import serve
from git.exc import GitCommandError
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIClient

from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import TokenFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.gis.models import ProjectGeoJSON
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.middleware import DRFWrapResponseMiddleware
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Format
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest
    from django.http import HttpResponse
    from gitlab.v4.objects.projects import Project as GitlabProject
    from rest_framework.authtoken.models import Token
    from sentry_sdk._types import Event
    from sentry_sdk._types import Hint

    from speleodb.users.models import User

BASE_DIR: pathlib.Path = pathlib.Path(__file__).parent / "artifacts"
COMMIT_FAILURE_MARKER: str = "SpeleoDB integration commit hook rejected upload"


class SentryEventTestCase(TransactionTestCase):
    """Observe native SDK event construction without substituting its transport.

    An empty DSN disables external delivery. The supported ``before_send`` hook
    observes the event and original exception produced by the real SDK; these
    assertions cover application reporting, not delivery to a Sentry server.
    """

    sentry_events: list[tuple[Event, Hint]]

    def setUp(self) -> None:
        super().setUp()
        self.sentry_events = []
        sentry_client: sentry_sdk.Client = sentry_sdk.Client(
            dsn="",
            default_integrations=False,
            auto_enabling_integrations=False,
            before_send=self._record_sentry_event,
        )
        self.addCleanup(sentry_client.close)
        scope: sentry_sdk.Scope = self.enterContext(sentry_sdk.isolation_scope())
        scope.set_client(sentry_client)

    def _record_sentry_event(self, event: Event, hint: Hint) -> Event:
        self.sentry_events.append((event, hint))
        return event

    def _reported_exception(self) -> BaseException:
        assert len(self.sentry_events) == 1, self.sentry_events
        event: Event
        hint: Hint
        event, hint = self.sentry_events[0]
        assert event.get("exception"), event
        exc_info = hint.get("exc_info")
        assert exc_info is not None
        exception: BaseException | None = exc_info[1]
        assert exception is not None
        return exception


@pytest.mark.skip_if_lighttest
class UploadErrorHandlingTests(SentryEventTestCase):
    """Require successful real provisioning before exercising upload failures."""

    client: APIClient
    user: User
    token: Token
    project: Project
    repo: GitRepo
    remote_project: GitlabProject
    original_head: str
    original_commit_ids: set[str]

    def setUp(self) -> None:
        super().setUp()
        assert connection.settings_dict["ATOMIC_REQUESTS"] is True
        assert not connection.in_atomic_block
        project_directory: str = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(
            override_settings(DJANGO_GIT_PROJECTS_DIR=pathlib.Path(project_directory))
        )
        self.client = APIClient(enforce_csrf_checks=False)
        self.user = UserFactory.create()
        self.token = TokenFactory.create(user=self.user)
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )
        self.project = ProjectFactory.create(
            created_by=self.user.email,
            type=ProjectType.ARIANE,
            exclude_geojson=True,
        )
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )
        self.project.acquire_mutex(self.user)

        # Any real provisioning/authentication failure fails setup. It cannot
        # accidentally satisfy a later assertion that an upload returned 500.
        self.repo = self.project.git_repo
        self.addCleanup(self.repo.close)
        remote_project: GitlabProject | None = GitlabManager._get_project(  # noqa: SLF001
            self.project
        )
        assert remote_project is not None
        self.remote_project = remote_project
        self.addCleanup(self.remote_project.delete)
        self.original_head = self.repo.head.commit.hexsha
        assert self._remote_head() == self.original_head
        self.project.construct_git_history_from_project(self.repo)
        self.original_commit_ids = set(
            ProjectCommit.objects.filter(project=self.project).values_list(
                "id", flat=True
            )
        )
        assert self.original_commit_ids == {self.original_head}
        assert not Format.objects.filter(project=self.project).exists()
        assert not ProjectGeoJSON.objects.filter(project=self.project).exists()

    def _remote_head(self) -> str:
        return str(
            self.remote_project.branches.get(settings.DJANGO_GIT_BRANCH_NAME).commit[
                "id"
            ]
        )

    def _do_upload(self, filename: str = "test_simple.tml") -> Response:
        artifact: SimpleUploadedFile = SimpleUploadedFile(
            filename,
            (BASE_DIR / "test_simple.tml").read_bytes(),
            content_type="application/octet-stream",
        )
        response = self.client.put(
            reverse(
                "api:v2:project-upload",
                kwargs={
                    "id": self.project.id,
                    "fileformat": FileFormat.ARIANE_TML.label.lower(),
                },
            ),
            {"artifact": artifact, "message": "integration failure upload"},
            format="multipart",
            headers={"authorization": f"Token {self.token.key}"},
        )
        assert isinstance(response, Response)
        return response

    def _assert_no_upload_writes(self) -> None:
        # TransactionTestCase lets the request transaction actually exit. Query
        # persisted rows instead of inspecting a surrounding test's rollback flag.
        assert not connection.in_atomic_block
        assert not connection.needs_rollback
        assert not Format.objects.filter(project=self.project).exists()
        assert not ProjectGeoJSON.objects.filter(project=self.project).exists()
        assert (
            set(
                ProjectCommit.objects.filter(project=self.project).values_list(
                    "id", flat=True
                )
            )
            == self.original_commit_ids
        )
        assert self._remote_head() == self.original_head

    def test_git_checkout_failure_logs_and_captures_sentry(self) -> None:
        index_lock: pathlib.Path = pathlib.Path(self.repo.git_dir) / "index.lock"
        index_lock.write_text("integration checkout lock\n")
        self.addCleanup(index_lock.unlink, missing_ok=True)

        with self.assertLogs("speleodb.api.v2.views.file", level="ERROR") as logs:
            response: Response = self._do_upload()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        exception: BaseException = self._reported_exception()
        assert isinstance(exception, GitCommandError), exception
        assert "index.lock" in str(exception)
        assert any("index.lock" in entry for entry in logs.output)
        assert self.repo.head.commit.hexsha == self.original_head
        self._assert_no_upload_writes()

    def test_git_failure_marks_transaction_for_rollback(self) -> None:
        hook: pathlib.Path = pathlib.Path(self.repo.git_dir) / "hooks/pre-commit"
        attempts: pathlib.Path = (
            pathlib.Path(self.repo.git_dir) / "upload-hook-attempts"
        )
        hook.write_text(
            "#!/bin/sh\n"
            "printf 'attempt\\n' >> .git/upload-hook-attempts\n"
            f"printf '{COMMIT_FAILURE_MARKER}\\n' >&2\n"
            "exit 1\n"
        )
        hook.chmod(0o755)

        response: Response = self._do_upload()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        # A failed initial checkout or a 429 cannot create this marker. It proves
        # the real commit command ran after the upload's Format row was inserted.
        assert (
            attempts.read_text().splitlines()
            == ["attempt"] * settings.DJANGO_GIT_RETRY_ATTEMPTS
        )
        exception: BaseException = self._reported_exception()
        assert isinstance(exception, GitCommandError), exception
        assert COMMIT_FAILURE_MARKER in str(exception)
        assert COMMIT_FAILURE_MARKER in str(response.data)
        self._assert_no_upload_writes()
        assert self.repo.head.commit.hexsha == self.original_head
        assert not self.repo.is_dirty(untracked_files=True)
        assert not (self.repo.path / "ariane.tml").exists()

    def test_gitlab_error_reports_to_sentry(self) -> None:
        # A real GitLab rejects the invalid credential. Reset cached connection
        # state so the application authenticates against the configured service.
        self.repo.close()
        shutil.rmtree(self.project.git_repo_dir)
        authenticated_client = GitlabManager._gl  # noqa: SLF001
        GitlabManager._gl = None  # noqa: SLF001
        GitlabManager._get_project.cache_clear()  # noqa: SLF001
        GitlabCredentials.get.cache_clear()
        try:
            with override_settings(GITLAB_TOKEN=uuid.uuid4().hex):
                response: Response = self._do_upload()
        finally:
            GitlabCredentials.get.cache_clear()
            GitlabManager._gl = authenticated_client  # noqa: SLF001

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        exception: BaseException = self._reported_exception()
        assert isinstance(exception, GitlabError), exception
        assert isinstance(
            exception.__cause__, gitlab.exceptions.GitlabAuthenticationError
        )
        assert exception.__cause__.response_code == status.HTTP_401_UNAUTHORIZED
        assert "problem accessing GitLab" in str(response.data)
        assert not self.project.git_repo_dir.exists()
        self._assert_no_upload_writes()

    def test_file_rejected_error_returns_415_without_sentry(self) -> None:
        response: Response = self._do_upload(filename="unsafe.sh")

        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        assert "rejected for security reasons" in str(response.data)
        assert not self.sentry_events
        self._assert_no_upload_writes()

    def test_validation_error_returns_400_without_sentry(self) -> None:
        response: Response = self._do_upload(filename="unsupported.invalid")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid file extension" in str(response.data)
        assert not self.sentry_events
        self._assert_no_upload_writes()


class ConstructGitHistorySavepointTests(TransactionTestCase):
    """A real foreign-key rejection must not poison the history transaction."""

    def test_integrity_error_does_not_break_transaction(self) -> None:
        if connection.vendor != "postgresql":
            pytest.skip("This regression exercises PostgreSQL immediate FK constraints")
        directory: str = self.enterContext(tempfile.TemporaryDirectory())
        repo: GitRepo = GitRepo.init(pathlib.Path(directory) / "history")
        self.addCleanup(repo.close)
        actor: git.Actor = git.Actor("History Test", "history@example.test")
        repo.index.commit("History FK constraint", author=actor, committer=actor)
        stale_project: Project = ProjectFactory.create()
        Project.objects.filter(id=stale_project.id).delete()

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            with pytest.raises(IntegrityError), transaction.atomic():
                ProjectCommit.get_or_create_from_commit(stale_project, repo.head.commit)

            stale_project.construct_git_history_from_project(repo)

            assert not connection.needs_rollback
            assert not ProjectCommit.objects.filter(id=repo.head.commit.hexsha).exists()
            surviving_project: Project = ProjectFactory.create()

        assert Project.objects.filter(id=surviving_project.id).exists()


class MiddlewareExceptionReportingTests(SentryEventTestCase):
    """Exercise v1/v2 routing with Django's real missing-file exception path."""

    def _middleware_and_request(
        self, route: str
    ) -> tuple[DRFWrapResponseMiddleware, Request]:
        directory: str = self.enterContext(tempfile.TemporaryDirectory())
        middleware: DRFWrapResponseMiddleware = DRFWrapResponseMiddleware(
            get_response=cast(
                "Callable[[HttpRequest], HttpResponse]",
                partial(
                    serve,
                    path="absent.txt",
                    document_root=directory,
                    show_indexes=False,
                ),
            )
        )
        request: Request = Request(RequestFactory().get(reverse(route)))
        return middleware, request

    def test_v1_middleware_captures_unhandled_exception(self) -> None:
        middleware: DRFWrapResponseMiddleware
        request: Request
        middleware, request = self._middleware_and_request("api:v1:projects")

        response = middleware(request)

        assert isinstance(response, Response)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        exception: BaseException = self._reported_exception()
        assert isinstance(exception, Http404)
        assert "absent.txt" in str(exception)
        assert response.data["success"] is False
        assert "absent.txt" in response.data["error"]
        assert response.data["url"].endswith(request.path)

    def test_v2_path_bypasses_middleware_sentry_capture(self) -> None:
        middleware: DRFWrapResponseMiddleware
        request: Request
        middleware, request = self._middleware_and_request("api:v2:projects")

        with pytest.raises(Http404, match=r"absent\.txt"):
            middleware(request)

        assert not self.sentry_events
