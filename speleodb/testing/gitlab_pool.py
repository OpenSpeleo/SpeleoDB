"""Four real GitLab repositories, leased and restored between isolated tests.

Only identifiers and Git baseline metadata live for the session. Django model
instances are reconstructed inside each test transaction, including after flush.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from functools import cache
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal
from uuid import UUID
from uuid import uuid4

import gitlab.exceptions
from allauth.account.models import EmailAddress
from django.conf import settings
from requests.exceptions import RequestException

from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.git_engine.client import GitlabClient
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import Project
from speleodb.surveys.models import UserProjectPermission
from speleodb.testing.gitlab_audit import creation_allocation
from speleodb.testing.gitlab_audit import get_ledger
from speleodb.testing.gitlab_audit import record_cleanup
from speleodb.users.models import User

if TYPE_CHECKING:
    from gitlab.v4.objects.projects import Project as RemoteProject


PROJECT_NAMES: dict[PermissionLevel, str] = {
    PermissionLevel.ADMIN: "ADMIN Project",
    PermissionLevel.READ_AND_WRITE: "Read and Write Project",
    PermissionLevel.READ_ONLY: "Read only Project",
    PermissionLevel.WEB_VIEWER: "Webviewer Project",
}
ALLOCATION_NAMES: dict[PermissionLevel, str] = {
    PermissionLevel.ADMIN: "canonical-admin",
    PermissionLevel.READ_AND_WRITE: "canonical-write",
    PermissionLevel.READ_ONLY: "canonical-read",
    PermissionLevel.WEB_VIEWER: "canonical-view",
}


@dataclass
class RepositorySlot:
    project_id: UUID = field(default_factory=uuid4)
    remote_id: int | None = None
    baseline_sha: str | None = None
    branch: str = ""


class GitlabPool:
    """A session owns four IDs; tests explicitly borrow existing remote state."""

    def __init__(self) -> None:
        self.slots: dict[PermissionLevel, RepositorySlot] = {
            role: RepositorySlot() for role in PROJECT_NAMES
        }
        self._client: GitlabClient | None = None
        self._credentials: GitlabCredentials | None = None
        self._directory: TemporaryDirectory[str] = TemporaryDirectory(
            prefix="speleodb-gitlab-pool-"
        )
        self._leased: set[PermissionLevel] = set()
        self._pending_restore: set[PermissionLevel] = set()

    @property
    def client(self) -> GitlabClient:
        if self._client is None:
            credentials: GitlabCredentials = GitlabCredentials.get()
            client = GitlabClient(
                f"{settings.GITLAB_HTTP_PROTOCOL}://{credentials.instance}",
                private_token=credentials.token,
                keep_base_url=settings.GITLAB_HTTP_PROTOCOL == "http",
            )
            client.auth()
            group = client.groups.get(str(credentials.group_id))
            assert group.full_path == credentials.group_name
            self._credentials = credentials
            self._client = client
        return self._client

    def project_id(self, role: PermissionLevel = PermissionLevel.ADMIN) -> UUID:
        return self.slots[role].project_id

    def model(self, role: PermissionLevel = PermissionLevel.ADMIN) -> Project:
        actor: str = "A" if role == PermissionLevel.ADMIN else "B"
        return Project(
            id=self.project_id(role),
            name=PROJECT_NAMES[role],
            description="Canonical CI survey project",
            created_by=f"ci-{actor.lower()}@example.test",
            country="MX",
            type=ProjectType.ARIANE,
        )

    def prepare(self, project: Project) -> None:
        """Provision once, without creating a checkout in the test directory."""
        role: PermissionLevel | None = next(
            (
                role
                for role, slot in self.slots.items()
                if slot.project_id == project.id
            ),
            None,
        )
        if role is None:
            raise AssertionError("Only canonical projects can borrow the GitLab pool")
        slot: RepositorySlot = self.slots[role]
        if slot.remote_id is None:
            self._provision(role, slot)
        assert slot.baseline_sha is not None, "GitLab pool initialization failed"
        if role in self._pending_restore:
            self._restore(slot)
            self._pending_restore.remove(role)
        self._leased.add(role)

    def _provision(self, role: PermissionLevel, slot: RepositorySlot) -> None:
        client: GitlabClient = self.client
        credentials: GitlabCredentials | None = self._credentials
        assert credentials is not None
        with creation_allocation(
            ALLOCATION_NAMES[role], credentials.group_id, str(slot.project_id)
        ):
            remote: RemoteProject = client.projects.create(
                {
                    "name": PROJECT_NAMES[role],
                    "path": str(slot.project_id),
                    "namespace_id": credentials.group_id,
                    "visibility": "private",
                    "builds_access_level": "disabled",
                    "merge_requests_access_level": "disabled",
                }
            )
        slot.remote_id = int(remote.id)
        slot.branch = str(settings.DJANGO_GIT_BRANCH_NAME)
        directory: Path = Path(self._directory.name) / str(slot.project_id)
        repository: GitRepo = GitRepo.init(directory)
        try:
            repository.git.symbolic_ref("HEAD", f"refs/heads/{slot.branch}")
            repository.create_remote("origin", credentials.project_url(slot.project_id))
            sha: str | None = repository.commit_and_push_project(
                message=settings.DJANGO_GIT_FIRST_COMMIT_MESSAGE,
                author_name="SpeleoDB CI",
                author_email=f"{slot.project_id}@ci.example.test",
                force_empty_commit=True,
            )
            assert sha is not None
            slot.baseline_sha = sha
        finally:
            repository.close()
        for branch in remote.protectedbranches.list(get_all=True):
            branch.delete()
        remote.default_branch = slot.branch
        remote.save()
        baselines: list[str] = [
            item.baseline_sha for item in self.slots.values() if item.baseline_sha
        ]
        assert len(baselines) == len(set(baselines))

    def release(self) -> None:
        """Restore only borrowed slots, including after a failing test."""
        errors: list[Exception] = []
        self._pending_restore.update(self._leased)
        self._leased.clear()
        try:
            for role in sorted(self._pending_restore):
                try:
                    self._restore(self.slots[role])
                except Exception as error:  # noqa: BLE001
                    errors.append(error)
                else:
                    self._pending_restore.remove(role)
        finally:
            GitlabManager._get_project.cache_clear()  # noqa: SLF001
            GitlabCredentials.get.cache_clear()
        if errors:
            raise ExceptionGroup("GitLab pool restoration failed", errors)

    def _restore(self, slot: RepositorySlot) -> None:
        assert slot.remote_id is not None
        assert slot.baseline_sha is not None
        remote: RemoteProject = self.client.projects.get(slot.remote_id)
        assert not remote.attributes.get("marked_for_deletion_at")
        remote.repository_access_level = "enabled"
        remote.builds_access_level = "disabled"
        remote.merge_requests_access_level = "disabled"
        for protected in remote.protectedbranches.list(get_all=True):
            protected.delete()
        remote.save()
        with GitRepo(Path(self._directory.name) / str(slot.project_id)) as repository:
            # REST branch metadata can lag a push. A force-with-lease must use
            # the Git transport's advertised ref, not the cached API snapshot.
            advertised: str = str(repository.git.ls_remote("--refs", "origin"))
            refs: dict[str, str] = {
                line.split()[1]: line.split()[0] for line in advertised.splitlines()
            }
            current: str = refs.get(f"refs/heads/{slot.branch}", "")
            if current != slot.baseline_sha:
                repository.git.push(
                    "origin",
                    f"{slot.baseline_sha}:refs/heads/{slot.branch}",
                    f"--force-with-lease=refs/heads/{slot.branch}:{current}",
                )
        remote.default_branch = slot.branch
        remote.save()
        for ref in refs:
            if ref.startswith("refs/heads/") and ref != f"refs/heads/{slot.branch}":
                remote.branches.delete(ref.removeprefix("refs/heads/"))
            elif ref.startswith("refs/tags/"):
                remote.tags.delete(ref.removeprefix("refs/tags/"))
        history: set[str] = {
            str(commit.id) for commit in remote.commits.list(get_all=True, all=True)
        }
        assert history == {slot.baseline_sha}, "Shared GitLab history was not restored"
        assert [branch.name for branch in remote.branches.list(get_all=True)] == [
            slot.branch
        ]
        assert not remote.tags.list(get_all=True)
        remote.refresh()
        assert remote.default_branch == slot.branch
        assert remote.repository_access_level == "enabled"
        assert remote.builds_access_level == "disabled"
        assert remote.merge_requests_access_level == "disabled"

    def close(self) -> None:
        errors: list[str] = []
        attempted_paths: set[str] = {
            row["path"]
            for row in get_ledger().summary()["allocations"]
            if row["attempts"]
        }
        try:
            for slot in self.slots.values():
                if (
                    slot.remote_id is None
                    and str(slot.project_id) not in attempted_paths
                ):
                    continue
                try:
                    if slot.remote_id is None:
                        # A timeout may occur after GitLab committed creation.
                        # Reconcile that exact identity before session cleanup.
                        assert self._credentials is not None
                        recovered: RemoteProject = self.client.projects.get(
                            f"{self._credentials.group_name}/{slot.project_id}"
                        )
                        slot.remote_id = int(recovered.id)
                    remote: RemoteProject = self.client.projects.get(slot.remote_id)
                    if not remote.attributes.get("marked_for_deletion_at"):
                        remote.delete()
                    remaining: RemoteProject = self.client.projects.get(slot.remote_id)
                    if remaining.attributes.get("marked_for_deletion_at"):
                        record_cleanup(slot.remote_id, "marked-for-deletion")
                    else:
                        record_cleanup(slot.remote_id, "still-active")
                        errors.append(f"{slot.remote_id}: deletion not confirmed")
                except gitlab.exceptions.GitlabGetError as error:
                    if error.response_code == HTTPStatus.NOT_FOUND:
                        record_cleanup(slot.remote_id or str(slot.project_id), "absent")
                    else:
                        errors.append(f"{slot.remote_id}: HTTP {error.response_code}")
                except (gitlab.exceptions.GitlabError, RequestException) as error:
                    errors.append(f"{slot.remote_id}: {type(error).__name__}")
        finally:
            if self._client is not None:
                self._client.session.close()
            self._directory.cleanup()
        assert not errors, f"GitLab pool cleanup failed: {errors}"


@cache
def get_pool() -> GitlabPool:
    return GitlabPool()


def canonical_user(actor: Literal["A", "B"] = "A") -> User:
    user, _ = User.objects.get_or_create(
        email=f"ci-{actor.lower()}@example.test",
        defaults={"name": f"CI User {actor}", "country": "MX"},
    )
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


def canonical_project(
    role: PermissionLevel = PermissionLevel.ADMIN, **overrides: Any
) -> Project:
    """Get a canonical DB row; permissions and live Git are explicit opt-ins."""
    if "id" in overrides or "pk" in overrides:
        raise ValueError("Use ProjectFactory for a distinct database-only identity")
    model: Project = get_pool().model(role)
    defaults: dict[str, Any] = {
        "name": model.name,
        "description": model.description,
        "country": model.country,
        "type": model.type,
        "created_by": model.created_by,
        **overrides,
    }
    project, created = Project.objects.get_or_create(id=model.id, defaults=defaults)
    if not created and overrides:
        for key, value in overrides.items():
            setattr(project, key, value)
        project.save(update_fields=list(overrides))
    return project


def project_matrix() -> dict[PermissionLevel, Project]:
    """The default A/B ownership and access matrix, entirely database-only."""
    user_a: User = canonical_user("A")
    user_b: User = canonical_user("B")
    projects: dict[PermissionLevel, Project] = {}
    for role in PROJECT_NAMES:
        project: Project = canonical_project(role)
        leader: User = user_a if role == PermissionLevel.ADMIN else user_b
        UserProjectPermission.objects.update_or_create(
            target=leader,
            project=project,
            defaults={"level": PermissionLevel.ADMIN, "is_active": True},
        )
        UserProjectPermission.objects.update_or_create(
            target=user_a,
            project=project,
            defaults={"level": role, "is_active": True},
        )
        projects[role] = project
    return projects
