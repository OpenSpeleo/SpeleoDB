# -*- coding: utf-8 -*-

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings

from speleodb.api.v2.tests.base_testcase import BaseProjectTestCaseMixin
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit


@pytest.mark.skip_if_lighttest
class TestPreloadGitHistory(BaseProjectTestCaseMixin):
    """Reconstruct SQL history from the configured GitLab service."""

    def setUp(self) -> None:
        super().setUp()
        self.root: Path = Path(
            self.enterContext(tempfile.TemporaryDirectory())
        ).resolve()
        self.working_dir: Path = self.root / "working"
        self.enterContext(override_settings(DJANGO_GIT_PROJECTS_DIR=self.working_dir))

    def _seed_remote(
        self, project: Project, messages: tuple[str, ...] = ()
    ) -> list[str]:
        GitlabManager.create_project(project)
        repo: GitRepo = GitRepo.init(project.git_repo_dir)
        self.addCleanup(repo.close)
        repo.create_remote("origin", GitlabCredentials.get().project_url(project.id))
        # Commit SHA is globally unique in the SQL cache. Distinct initial trees
        # preserve each project's root even when initialized in the same second.
        (repo.path / "README.txt").write_text(
            f"Project {project.id}\n", encoding="utf-8"
        )
        repo.publish_first_commit()
        hashes: list[str] = [repo.head.commit.hexsha]
        for index, message in enumerate(messages):
            (repo.path / "README.txt").write_text(
                f"Project {project.id}, revision {index}\n", encoding="utf-8"
            )
            commit: str | None = repo.commit_and_push_project(
                message, author_name=self.user.name, author_email=self.user.email
            )
            assert commit is not None
            hashes.append(commit)
        return hashes

    def _assert_history(self, project: Project, hashes: list[str]) -> None:
        commits = ProjectCommit.objects.filter(project=project)
        assert set(commits.values_list("id", flat=True)) == set(hashes)
        # The command owns and removes its working copy, but not the remote.
        assert not project.git_repo_dir.exists()
        # Clone again from GitLab: cleanup must not delete remote history.
        with tempfile.TemporaryDirectory() as directory:
            remote: GitRepo = GitRepo.clone_from(
                GitlabCredentials.get().project_url(project.id),
                Path(directory),
                branch=settings.DJANGO_GIT_BRANCH_NAME,
            )
            try:
                assert {commit.hexsha for commit in remote.iter_commits()} == set(
                    hashes
                )
            finally:
                remote.close()

    def test_preload_no_commits(self) -> None:
        """Cache the initial Git commit when there are no user commits."""
        hashes: list[str] = self._seed_remote(self.project)
        assert not ProjectCommit.objects.filter(project=self.project).exists()

        call_command("preload_git_history")

        self._assert_history(self.project, hashes)
        assert ProjectCommit.objects.get(id=hashes[0]).message == (
            settings.DJANGO_GIT_FIRST_COMMIT_MESSAGE
        )

    def test_preload_with_commits(self) -> None:
        """Rebuild deleted cache rows from the remote's complete history."""
        hashes: list[str] = self._seed_remote(self.project, ("User commit",))

        call_command("preload_git_history")
        self._assert_history(self.project, hashes)
        ProjectCommit.objects.filter(project=self.project).delete()

        call_command("preload_git_history")

        self._assert_history(self.project, hashes)
        user_commit: ProjectCommit = ProjectCommit.objects.get(id=hashes[-1])
        assert user_commit.message == "User commit"
        assert user_commit.parent_ids == [hashes[0]]
        assert user_commit.author_email == self.user.email

    def test_preload_multiple_projects(self) -> None:
        project2: Project = ProjectFactory.create(created_by=self.user.email)
        hashes1: list[str] = self._seed_remote(self.project, ("Project 1 Commit",))
        hashes2: list[str] = self._seed_remote(project2, ("Project 2 Commit",))

        call_command("preload_git_history")
        ProjectCommit.objects.all().delete()

        call_command("preload_git_history")

        self._assert_history(self.project, hashes1)
        self._assert_history(project2, hashes2)
        assert ProjectCommit.objects.get(id=hashes1[-1]).message == "Project 1 Commit"
        assert ProjectCommit.objects.get(id=hashes2[-1]).message == "Project 2 Commit"

    def test_preload_is_idempotent_after_working_copy_cleanup(self) -> None:
        hashes: list[str] = self._seed_remote(self.project, ("User commit",))

        call_command("preload_git_history")
        self._assert_history(self.project, hashes)

        call_command("preload_git_history")

        self._assert_history(self.project, hashes)

    def test_preload_continues_after_project_failure(self) -> None:
        broken_project: Project = ProjectFactory.create(created_by=self.user.email)
        hashes: list[str] = self._seed_remote(self.project)

        broken_repo: GitRepo = broken_project.git_repo
        self.addCleanup(broken_repo.close)
        broken_repo.remotes.origin.set_url(str(self.root / "missing.git"))
        self.enterContext(
            override_settings(
                DJANGO_GIT_RETRY_BASE_DELAY_SECONDS=0.01,
                DJANGO_GIT_RETRY_MAX_DELAY_SECONDS=0.02,
            )
        )
        with self.assertLogs(
            "speleodb.common.management.commands.preload_git_history", level="ERROR"
        ) as logs:
            call_command("preload_git_history")

        self._assert_history(self.project, hashes)
        assert not broken_project.git_repo_dir.exists()
        assert not ProjectCommit.objects.filter(project=broken_project).exists()
        assert "does not appear to be a git repository" in "\n".join(logs.output)
