"""Database isolation and permission contracts for the shared CI projects."""

from __future__ import annotations

from contextlib import closing
from typing import TYPE_CHECKING
from typing import override
from uuid import uuid4

import pytest
from django.conf import settings
from django.db import connection
from django.db import transaction
from django.test.utils import CaptureQueriesContext

from speleodb.api.v2.tests.factories import CanonicalProjectFactory
from speleodb.api.v2.tests.factories import CylinderInstallFactory
from speleodb.api.v2.tests.factories import ExplorationLeadFactory
from speleodb.api.v2.tests.factories import ProjectCommitFactory
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import SubSurfaceStationFactory
from speleodb.api.v2.tests.factories import TeamProjectPermissionFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.surveys.models import Project
from speleodb.surveys.models import UserProjectPermission
from speleodb.testing.gitlab_audit import get_ledger
from speleodb.testing.gitlab_pool import PROJECT_NAMES
from speleodb.testing.gitlab_pool import GitlabPool
from speleodb.testing.gitlab_pool import RepositorySlot
from speleodb.testing.gitlab_pool import canonical_project
from speleodb.testing.gitlab_pool import canonical_user
from speleodb.testing.gitlab_pool import get_pool
from speleodb.testing.gitlab_pool import project_matrix
from speleodb.users.models import User

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from uuid import UUID

    from gitlab.v4.objects.projects import Project as RemoteProject

    from speleodb.gis.models import CylinderInstall
    from speleodb.gis.models import ExplorationLead
    from speleodb.gis.models import SubSurfaceStation
    from speleodb.surveys.models import ProjectCommit
    from speleodb.surveys.models import TeamProjectPermission


pytestmark = pytest.mark.django_db


class RestoreStatePool(GitlabPool):
    """Exercise lease state without replacing any SDK or HTTP response."""

    def __init__(self) -> None:
        super().__init__()
        self.failed_roles: set[PermissionLevel] = set()
        self.restored_roles: list[PermissionLevel] = []
        for index, slot in enumerate(self.slots.values(), start=1):
            slot.remote_id = index
            slot.baseline_sha = f"baseline-{index}"

    @override
    def _restore(self, slot: RepositorySlot) -> None:
        role: PermissionLevel = next(
            role for role, candidate in self.slots.items() if candidate is slot
        )
        self.restored_roles.append(role)
        if role in self.failed_roles:
            raise RuntimeError(f"Restore failed for {role.name}")


@pytest.fixture
def state_pool() -> Iterator[RestoreStatePool]:
    pool: RestoreStatePool = RestoreStatePool()
    try:
        yield pool
    finally:
        # These IDs are state-machine inputs, never live remote ownership.
        pool._directory.cleanup()  # noqa: SLF001


def test_failed_release_still_restores_every_other_borrowed_role(
    state_pool: RestoreStatePool,
) -> None:
    for role in PROJECT_NAMES:
        state_pool.prepare(state_pool.model(role))
    state_pool.failed_roles = {PermissionLevel.WEB_VIEWER, PermissionLevel.READ_ONLY}

    with pytest.raises(ExceptionGroup, match="restoration failed") as raised:
        state_pool.release()

    assert len(raised.value.exceptions) == len(state_pool.failed_roles)
    assert state_pool.restored_roles == sorted(PROJECT_NAMES)
    state_pool.restored_roles.clear()
    state_pool.failed_roles.clear()
    state_pool.release()
    assert state_pool.restored_roles == [
        PermissionLevel.WEB_VIEWER,
        PermissionLevel.READ_ONLY,
    ]


def test_failed_role_requires_successful_reset_before_next_lease(
    state_pool: RestoreStatePool,
) -> None:
    project: Project = state_pool.model(PermissionLevel.READ_AND_WRITE)
    state_pool.prepare(project)
    state_pool.failed_roles.add(PermissionLevel.READ_AND_WRITE)
    with pytest.raises(ExceptionGroup, match="restoration failed"):
        state_pool.release()

    with pytest.raises(RuntimeError, match="READ_AND_WRITE"):
        state_pool.prepare(project)

    state_pool.failed_roles.clear()
    state_pool.restored_roles.clear()
    state_pool.prepare(project)
    assert state_pool.restored_roles == [PermissionLevel.READ_AND_WRITE]
    state_pool.restored_roles.clear()
    state_pool.prepare(project)
    assert state_pool.restored_roles == []


def test_repeated_prepare_does_not_reset_a_healthy_active_lease(
    state_pool: RestoreStatePool,
) -> None:
    project: Project = state_pool.model()
    state_pool.prepare(project)
    state_pool.prepare(project)
    assert state_pool.restored_roles == []


def test_named_projects_reuse_ids_after_database_deletion() -> None:
    original: Project = canonical_project(PermissionLevel.READ_ONLY)
    original_id: UUID = original.id
    original.delete()

    reconstructed: Project = canonical_project(PermissionLevel.READ_ONLY)

    assert reconstructed.id == original_id
    assert reconstructed.name == "Read only Project"
    assert reconstructed is not original
    assert Project.objects.count() == 1


def test_repeated_requests_preserve_changes_and_apply_explicit_overrides() -> None:
    first: Project = canonical_project(description="Initial description")
    first.name = "Scenario-specific name"
    first.save(update_fields=["name"])

    reused: Project = canonical_project(description="Updated description")

    assert reused.id == first.id
    assert reused.name == "Scenario-specific name"
    assert reused.description == "Updated description"
    assert Project.objects.count() == 1


def test_rolled_back_changes_do_not_leak_through_cached_model_instances() -> None:
    original: Project = canonical_project()
    with transaction.atomic():
        changed: Project = canonical_project(name="Rolled-back name")
        assert changed.name == "Rolled-back name"
        transaction.set_rollback(True)

    restored: Project = canonical_project()

    assert restored.id == original.id
    assert restored.name == "ADMIN Project"


def test_matrix_has_exact_ownership_and_access_without_remote_creation() -> None:
    before: dict[str, object] = get_ledger().summary()
    remote_ids: list[int | None] = [
        slot.remote_id for slot in get_pool().slots.values()
    ]

    projects: dict[PermissionLevel, Project] = project_matrix()
    user_a: User = canonical_user("A")
    user_b: User = canonical_user("B")

    assert set(projects) == set(PermissionLevel)
    assert Project.objects.count() == len(PROJECT_NAMES)
    assert User.objects.count() == 2  # noqa: PLR2004
    for role, project in projects.items():
        assert project.name == PROJECT_NAMES[role]
        assert project.created_by == (
            user_a.email if role == PermissionLevel.ADMIN else user_b.email
        )
        expected: dict[int, int] = {user_a.pk: role}
        if role != PermissionLevel.ADMIN:
            expected[user_b.pk] = PermissionLevel.ADMIN
        assert (
            dict(
                UserProjectPermission.objects.filter(
                    project=project, is_active=True
                ).values_list("target_id", "level")
            )
            == expected
        )

    assert get_ledger().summary() == before
    assert [slot.remote_id for slot in get_pool().slots.values()] == remote_ids
    assert all(not project.git_repo_dir.exists() for project in projects.values())


def test_repeated_matrix_requests_keep_one_permission_per_actor_and_project() -> None:
    first: dict[PermissionLevel, Project] = project_matrix()
    second: dict[PermissionLevel, Project] = project_matrix()

    assert {role: project.id for role, project in first.items()} == {
        role: project.id for role, project in second.items()
    }
    assert UserProjectPermission.objects.count() == 7  # noqa: PLR2004


def test_child_factories_share_a_project_and_allow_explicit_distinct_projects() -> None:
    project: Project = canonical_project()
    station: SubSurfaceStation = SubSurfaceStationFactory.create()
    lead: ExplorationLead = ExplorationLeadFactory.create()
    commit: ProjectCommit = ProjectCommitFactory.create()
    user_permission: UserProjectPermission = UserProjectPermissionFactory.create()
    team_permission: TeamProjectPermission = TeamProjectPermissionFactory.create()
    install: CylinderInstall = CylinderInstallFactory.create()

    assert {
        station.project_id,
        lead.project_id,
        commit.project_id,
        user_permission.project_id,
        team_permission.project_id,
        install.project_id,
    } == {project.id}
    assert Project.objects.count() == 1

    distinct: Project = ProjectFactory.create()
    other_station: SubSurfaceStation = SubSurfaceStationFactory.create(project=distinct)

    assert distinct.id != project.id
    assert other_station.project_id == distinct.id
    assert not distinct.git_repo_dir.exists()


def test_commit_factory_build_does_not_persist_its_default_project() -> None:
    with CaptureQueriesContext(connection) as queries:
        commit: ProjectCommit = ProjectCommitFactory.build()

    assert len(queries) == 0
    assert commit.project_id == get_pool().project_id()
    assert not Project.objects.filter(id=commit.project_id).exists()


@pytest.mark.parametrize("strategy", ["build", "create"])
@pytest.mark.parametrize("identity_field", ["id", "pk"])
def test_canonical_factory_rejects_identity_overrides(
    strategy: str, identity_field: str
) -> None:
    with pytest.raises(ValueError, match="ProjectFactory"):
        getattr(CanonicalProjectFactory, strategy)(**{identity_field: uuid4()})


@pytest.mark.skip_if_lighttest
def test_live_roles_have_distinct_empty_initial_commits() -> None:
    pool: GitlabPool = get_pool()
    hashes: set[str] = set()
    remote_ids: set[int] = set()
    for role in PROJECT_NAMES:
        project: Project = canonical_project(role)
        pool.prepare(project)
        with closing(project.git_repo) as repository:
            assert repository.head.commit.message.strip() == (
                settings.DJANGO_GIT_FIRST_COMMIT_MESSAGE
            )
            assert list(repository.head.commit.tree) == []
            assert len(list(repository.iter_commits())) == 1
            hashes.add(repository.head.commit.hexsha)
            ProjectCommitFactory.create(
                id=repository.head.commit.hexsha, project=project
            )
        remote_id: int | None = pool.slots[role].remote_id
        assert remote_id is not None
        remote_ids.add(remote_id)

    assert len(hashes) == len(PROJECT_NAMES)
    assert len(remote_ids) == len(PROJECT_NAMES)


@pytest.mark.skip_if_lighttest
def test_live_lease_restores_history_branches_tags_and_contents(tmp_path: Path) -> None:
    pool: GitlabPool = get_pool()
    project: Project = canonical_project(PermissionLevel.READ_AND_WRITE)
    pool.prepare(project)
    remote_id: int | None = pool.slots[PermissionLevel.READ_AND_WRITE].remote_id
    assert remote_id is not None
    remote: RemoteProject = pool.client.projects.get(remote_id)
    before: dict[str, object] = get_ledger().summary()

    with closing(project.git_repo) as repository:
        baseline: str = repository.head.commit.hexsha
        (repository.path / "scenario.txt").write_text(
            "Only this test may see this content", encoding="utf-8"
        )
        changed: str | None = repository.commit_and_push_project(
            "Temporary scenario history",
            author_name="CI User A",
            author_email=canonical_user("A").email,
        )
        assert changed is not None
        assert changed != baseline
        repository.git.push("origin", "HEAD:refs/heads/scenario-branch")
        repository.git.push("origin", "HEAD:refs/tags/scenario-tag")

    assert remote.tags.get("scenario-tag").commit["id"] == changed
    assert remote.branches.get("scenario-branch").commit["id"] == changed

    pool.release()
    pool.prepare(project)

    with closing(
        GitRepo.clone_from(
            GitlabCredentials.get().project_url(project.id),
            tmp_path / "next-lease",
            branch=settings.DJANGO_GIT_BRANCH_NAME,
        )
    ) as restored:
        assert restored.head.commit.hexsha == baseline
        assert list(restored.head.commit.tree) == []
        assert not (restored.path / "scenario.txt").exists()
        assert len(list(restored.iter_commits())) == 1
    assert [branch.name for branch in remote.branches.list(get_all=True)] == [
        settings.DJANGO_GIT_BRANCH_NAME
    ]
    assert remote.tags.list(get_all=True) == []
    assert get_ledger().summary() == before
