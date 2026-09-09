# -*- coding: utf-8 -*-

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import git
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings

from speleodb.api.v2.tests.base_testcase import BaseProjectTestCaseMixin
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.exceptions import GitBaseError
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit


class TestPreloadGitHistory(BaseProjectTestCaseMixin):
    """Exercise real Git history reconstruction without external services."""

    def setUp(self) -> None:
        super().setUp()
        self.root: Path = Path(
            self.enterContext(tempfile.TemporaryDirectory())
        ).resolve()
        self.working_dir: Path = self.root / "working"
        self.enterContext(override_settings(DJANGO_GIT_PROJECTS_DIR=self.working_dir))
        self.clone: MagicMock = self.enterContext(
            patch.object(
                GitlabManager,
                "create_or_clone_project",
                side_effect=self._clone_local_project,
            )
        )

    def _seed_remote(
        self, project: Project, messages: tuple[str, ...] = ()
    ) -> list[str]:
        remote_path: Path = self.root / "remotes" / str(project.id)
        seed_path: Path = self.root / "seeds" / str(project.id)
        branch: str = settings.DJANGO_GIT_BRANCH_NAME
        remote: git.Repo = git.Repo.init(remote_path, bare=True, initial_branch=branch)
        seed: git.Repo = git.Repo.init(seed_path, initial_branch=branch)
        self.addCleanup(remote.close)
        self.addCleanup(seed.close)
        actor: git.Actor = git.Actor(self.user.name, self.user.email)
        hashes: list[str] = []
        for index, message in enumerate(
            (settings.DJANGO_GIT_FIRST_COMMIT_MESSAGE, *messages)
        ):
            # ProjectCommit's primary key is the SHA across all projects.
            # Make even initial commits unique when created in the same second.
            (seed_path / "README.txt").write_text(
                f"Project {project.id}, revision {index}\n", encoding="utf-8"
            )
            seed.index.add(["README.txt"])
            commit: git.Commit = seed.index.commit(
                message, author=actor, committer=actor
            )
            hashes.append(commit.hexsha)
        seed.create_remote("origin", str(remote_path))
        seed.git.push("origin", branch)
        return hashes

    def _clone_local_project(self, project: Project) -> GitRepo:
        self.working_dir.mkdir(parents=True, exist_ok=True)
        return GitRepo.clone_from(
            url=str(self.root / "remotes" / str(project.id)),
            to_path=project.git_repo_dir,
        )

    def _assert_history(self, project: Project, hashes: list[str]) -> None:
        commits = ProjectCommit.objects.filter(project=project)
        assert set(commits.values_list("id", flat=True)) == set(hashes)
        # The command owns and removes its working copy, but not the remote.
        assert not project.git_repo_dir.exists()
        assert (self.root / "remotes" / str(project.id)).exists()

    def test_preload_no_commits(self) -> None:
        """Cache the initial Git commit when there are no user commits."""
        hashes: list[str] = self._seed_remote(self.project)
        assert not ProjectCommit.objects.filter(project=self.project).exists()

        call_command("preload_git_history")

        self._assert_history(self.project, hashes)
        assert ProjectCommit.objects.get(id=hashes[0]).message == (
            settings.DJANGO_GIT_FIRST_COMMIT_MESSAGE
        )
        self.clone.assert_called_once()

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
        assert self.clone.call_count == 2  # noqa: PLR2004

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
        assert self.clone.call_count == 2  # noqa: PLR2004

    def test_preload_continues_after_project_failure(self) -> None:
        broken_project: Project = ProjectFactory.create(created_by=self.user.email)
        hashes: list[str] = self._seed_remote(self.project)

        def clone_with_failure(project: Project) -> GitRepo:
            if project.id == broken_project.id:
                project.git_repo_dir.mkdir(parents=True, exist_ok=True)
                raise GitBaseError("simulated clone failure")
            return self._clone_local_project(project)

        self.clone.side_effect = clone_with_failure
        with self.assertLogs(
            "speleodb.common.management.commands.preload_git_history", level="ERROR"
        ) as logs:
            call_command("preload_git_history")

        self._assert_history(self.project, hashes)
        assert not broken_project.git_repo_dir.exists()
        assert not ProjectCommit.objects.filter(project=broken_project).exists()
        assert "simulated clone failure" in "\n".join(logs.output)
