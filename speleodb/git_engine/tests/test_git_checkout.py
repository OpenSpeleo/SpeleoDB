# -*- coding: utf-8 -*-

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import PropertyMock
from unittest.mock import patch

import git
import pytest
from django.conf import settings
from django.test import override_settings
from git.exc import GitCommandError

from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.exceptions import GitBaseError
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Project


class GitCheckoutTests(TestCase):
    """Exercise branch selection and publication against local bare remotes."""

    def setUp(self) -> None:
        super().setUp()
        self.root: Path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.branch: str = "configured-main"
        self.enterContext(override_settings(DJANGO_GIT_BRANCH_NAME=self.branch))
        self.actor: git.Actor = git.Actor("Test Author", "test@example.invalid")
        self.remote: git.Repo = git.Repo.init(
            self.root / "remote.git", bare=True, initial_branch=self.branch
        )
        self.seed: git.Repo = git.Repo.init(
            self.root / "seed", initial_branch=self.branch
        )
        self.addCleanup(self.remote.close)
        self.addCleanup(self.seed.close)
        self.seed.create_remote("origin", str(self.remote.git_dir))

    def _push_revision(self, content: str) -> str:
        (self.root / "seed" / "README.txt").write_text(content, encoding="utf-8")
        self.seed.index.add(["README.txt"])
        commit: git.Commit = self.seed.index.commit(
            content, author=self.actor, committer=self.actor
        )
        self.seed.git.push("origin", self.seed.active_branch.name)
        return commit.hexsha

    def _clone(self) -> GitRepo:
        repo: GitRepo = GitRepo.clone_from(
            url=str(self.remote.git_dir), to_path=self.root / "working"
        )
        self.addCleanup(repo.close)
        return repo

    def _assert_published_initial_commit(self, repo: GitRepo) -> None:
        assert repo.active_branch.name == self.branch
        assert self.remote.commit(self.branch).hexsha == repo.head.commit.hexsha
        assert repo.head.commit.message == settings.DJANGO_GIT_FIRST_COMMIT_MESSAGE
        assert len(list(self.remote.iter_commits(self.branch))) == 1

    def test_new_repository_publishes_without_pulling_empty_remote(self) -> None:
        repo: GitRepo = GitRepo.init(self.root / "working")
        self.addCleanup(repo.close)
        repo.create_remote("origin", str(self.remote.git_dir))

        with (
            patch.object(git.Remote, "pull", side_effect=AssertionError("empty pull")),
            patch.object(
                git.Remote, "fetch", side_effect=AssertionError("empty fetch")
            ),
        ):
            repo.publish_first_commit()

        self._assert_published_initial_commit(repo)

    def test_empty_clone_publishes_configured_initial_branch(self) -> None:
        repo: GitRepo = self._clone()
        assert not repo.head.is_valid()

        with (
            patch.object(git.Remote, "pull", side_effect=AssertionError("empty pull")),
            patch.object(
                git.Remote, "fetch", side_effect=AssertionError("empty fetch")
            ),
        ):
            repo.publish_first_commit()

        self._assert_published_initial_commit(repo)

    def test_publication_rejects_existing_history(self) -> None:
        original_sha: str = self._push_revision("existing history")
        repo: GitRepo = self._clone()

        with pytest.raises(GitBaseError):
            repo.publish_first_commit()

        assert repo.head.commit.hexsha == original_sha
        assert self.remote.commit(self.branch).hexsha == original_sha

    def test_initial_publication_propagates_push_failure(self) -> None:
        repo: GitRepo = GitRepo.init(self.root / "working")
        self.addCleanup(repo.close)
        repo.create_remote("origin", str(self.remote.git_dir))

        with (
            patch.object(
                git.Git,
                "push",
                create=True,
                side_effect=GitCommandError("push", 128, stderr="503 unavailable"),
            ),
            patch("speleodb.utils.helpers.time.sleep"),
            pytest.raises(GitBaseError),
        ):
            repo.publish_first_commit()

        assert repo.head.is_valid()
        assert repo.active_branch.name == self.branch
        assert not self.remote.heads

    def test_invalid_remote_head_does_not_mean_empty_repository(self) -> None:
        original_sha: str = self._push_revision("existing history")
        self.remote.git.symbolic_ref("HEAD", "refs/heads/missing")
        repo: GitRepo = self._clone()
        assert not repo.head.is_valid()
        assert repo.remotes.origin.refs

        with pytest.raises(GitBaseError):
            repo.publish_first_commit()

        assert self.remote.commit(self.branch).hexsha == original_sha
        assert not repo.head.is_valid()

    def test_return_from_historical_commit_pulls_default_branch_updates(self) -> None:
        original_sha: str = self._push_revision("first version")
        repo: GitRepo = self._clone()
        repo.checkout_commit(original_sha)
        assert repo.head.is_detached
        latest_sha: str = self._push_revision("latest version")

        repo.checkout_default_branch_and_pull()

        assert repo.active_branch.name == self.branch
        assert repo.head.commit.hexsha == latest_sha
        assert (repo.path / "README.txt").read_text(
            encoding="utf-8"
        ) == "latest version"

    def test_missing_local_branch_uses_updated_remote_tracking_ref(self) -> None:
        original_sha: str = self._push_revision("first version")
        repo: GitRepo = self._clone()
        repo.git.checkout(original_sha)
        repo.delete_head(self.branch, force=True)
        latest_sha: str = self._push_revision("latest version")

        repo.checkout_default_branch_and_pull()

        assert repo.active_branch.name == self.branch
        assert repo.head.commit.hexsha == latest_sha
        tracking_branch: git.RemoteReference | None = (
            repo.active_branch.tracking_branch()
        )
        assert tracking_branch is not None
        assert tracking_branch.name == f"origin/{self.branch}"

    def test_missing_remote_branch_is_not_created_from_current_head(self) -> None:
        original_sha: str = self._push_revision("first version")
        repo: GitRepo = self._clone()
        repo.git.checkout("-b", "other")
        repo.delete_head(self.branch, force=True)
        self.remote.git.update_ref("-d", f"refs/heads/{self.branch}")
        sentinel: Path = repo.path / "local-work.txt"
        sentinel.write_text("keep me", encoding="utf-8")

        with pytest.raises(GitBaseError):
            repo.checkout_default_branch_and_pull()

        assert repo.active_branch.name == "other"
        assert repo.head.commit.hexsha == original_sha
        assert self.branch not in repo.heads
        assert sentinel.read_text(encoding="utf-8") == "keep me"

    def test_dirty_default_checkout_preserves_files_without_fetching(self) -> None:
        original_sha: str = self._push_revision("first version")
        self._push_revision("latest version")
        repo: GitRepo = self._clone()
        repo.git.checkout(original_sha)
        readme: Path = repo.path / "README.txt"
        readme.write_text("uncommitted changes", encoding="utf-8")

        with (
            patch.object(
                git.Remote, "pull", side_effect=AssertionError("unexpected pull")
            ),
            patch.object(
                git.Remote, "fetch", side_effect=AssertionError("unexpected fetch")
            ),
            pytest.raises(GitCommandError),
        ):
            repo.checkout_default_branch_and_pull()

        assert repo.head.is_detached
        assert repo.head.commit.hexsha == original_sha
        assert readme.read_text(encoding="utf-8") == "uncommitted changes"

    def test_dirty_commit_checkout_is_not_treated_as_missing_commit(self) -> None:
        original_sha: str = self._push_revision("first version")
        latest_sha: str = self._push_revision("latest version")
        repo: GitRepo = self._clone()
        readme: Path = repo.path / "README.txt"
        readme.write_text("uncommitted changes", encoding="utf-8")

        with (
            patch.object(
                git.Remote, "pull", side_effect=AssertionError("unexpected pull")
            ),
            patch.object(
                git.Remote, "fetch", side_effect=AssertionError("unexpected fetch")
            ),
            pytest.raises(GitCommandError),
        ):
            repo.checkout_commit(original_sha)

        assert repo.active_branch.name == self.branch
        assert repo.head.commit.hexsha == latest_sha
        assert readme.read_text(encoding="utf-8") == "uncommitted changes"

    def test_existing_commit_checkout_does_not_contact_remote(self) -> None:
        original_sha: str = self._push_revision("first version")
        self._push_revision("latest version")
        repo: GitRepo = self._clone()

        with (
            patch.object(
                git.Remote, "pull", side_effect=AssertionError("unexpected pull")
            ),
            patch.object(
                git.Remote, "fetch", side_effect=AssertionError("unexpected fetch")
            ),
        ):
            repo.checkout_commit(original_sha)

        assert repo.head.is_detached
        assert repo.head.commit.hexsha == original_sha

    def test_missing_commit_is_fetched_before_checkout(self) -> None:
        self._push_revision("first version")
        repo: GitRepo = self._clone()
        latest_sha: str = self._push_revision("latest version")

        repo.checkout_commit(latest_sha)

        assert repo.head.is_detached
        assert repo.head.commit.hexsha == latest_sha

    def test_latest_download_restores_default_branch_and_pulls_updates(self) -> None:
        original_sha: str = self._push_revision("first version")
        repo: GitRepo = self._clone()
        repo.checkout_commit(original_sha)
        latest_sha: str = self._push_revision("latest version")
        repo.remotes.origin.set_url(str(self.root / "missing.git"))
        processor: BaseFileProcessor = BaseFileProcessor(Project(name="Test"))
        processor.TARGET_SAVE_FILENAME = "README.txt"
        target: Path = self.root / "download.txt"

        with (
            patch.object(
                Project, "git_repo", new_callable=PropertyMock, return_value=repo
            ),
            patch.object(
                GitlabCredentials, "project_url", return_value=str(self.remote.git_dir)
            ),
        ):
            filename: str = processor.get_filename_for_download(target)

        assert filename == target.name
        assert target.read_text(encoding="utf-8") == "latest version"
        assert repo.active_branch.name == self.branch
        assert repo.head.commit.hexsha == latest_sha
        assert repo.remotes.origin.url == str(self.remote.git_dir)

    def test_commit_download_fetches_missing_objects_without_moving_head(self) -> None:
        original_sha: str = self._push_revision("first version")
        repo: GitRepo = self._clone()
        repo.checkout_commit(original_sha)
        latest_sha: str = self._push_revision("latest version")
        invalid_origin: str = str(self.root / "missing.git")
        repo.remotes.origin.set_url(invalid_origin)
        processor: BaseFileProcessor = BaseFileProcessor(Project(name="Test"))
        processor.TARGET_SAVE_FILENAME = "README.txt"
        target: Path = self.root / "download.txt"

        with (
            patch.object(
                Project, "git_repo", new_callable=PropertyMock, return_value=repo
            ),
            patch.object(
                GitlabCredentials, "project_url", return_value=str(self.remote.git_dir)
            ),
        ):
            filename: str = processor.get_filename_for_download(
                target, hexsha=latest_sha
            )

        assert filename == target.name
        assert target.read_text(encoding="utf-8") == "latest version"
        assert repo.head.is_detached
        assert repo.head.commit.hexsha == original_sha
        assert (repo.path / "README.txt").read_text(encoding="utf-8") == "first version"
        assert repo.remotes.origin.url == str(self.remote.git_dir)

        # The fetched commit is now local: another download needs neither
        # remote configuration repair nor a network request.
        repo.remotes.origin.set_url(invalid_origin)
        with (
            patch.object(
                Project, "git_repo", new_callable=PropertyMock, return_value=repo
            ),
            patch.object(Project, "ensure_git_origin") as repair,
            patch.object(
                GitRepo, "fetch", side_effect=AssertionError("unexpected fetch")
            ),
            patch.object(
                GitRepo, "pull", side_effect=AssertionError("unexpected pull")
            ),
        ):
            processor.get_filename_for_download(target, hexsha=latest_sha)

        repair.assert_not_called()
        assert target.read_text(encoding="utf-8") == "latest version"
        assert repo.remotes.origin.url == invalid_origin
        assert repo.head.is_detached
        assert repo.head.commit.hexsha == original_sha

    def test_pull_outage_preserves_existing_branch_and_files(self) -> None:
        original_sha: str = self._push_revision("first version")
        repo: GitRepo = self._clone()
        sentinel: Path = repo.path / "local-work.txt"
        sentinel.write_text("keep me", encoding="utf-8")

        with (
            patch.object(
                git.Remote,
                "pull",
                side_effect=GitCommandError("pull", 128, stderr="503 unavailable"),
            ),
            patch("speleodb.utils.helpers.time.sleep"),
            pytest.raises(GitBaseError),
        ):
            repo.checkout_default_branch_and_pull()

        assert repo.active_branch.name == self.branch
        assert repo.head.commit.hexsha == original_sha
        assert sentinel.read_text(encoding="utf-8") == "keep me"

    def test_fetch_outage_does_not_create_missing_branch(self) -> None:
        original_sha: str = self._push_revision("first version")
        repo: GitRepo = self._clone()
        repo.git.checkout(original_sha)
        repo.delete_head(self.branch, force=True)
        sentinel: Path = repo.path / "local-work.txt"
        sentinel.write_text("keep me", encoding="utf-8")

        with (
            patch.object(
                git.Remote,
                "fetch",
                side_effect=GitCommandError("fetch", 128, stderr="503 unavailable"),
            ),
            patch("speleodb.utils.helpers.time.sleep"),
            pytest.raises(GitBaseError),
        ):
            repo.checkout_default_branch_and_pull()

        assert repo.head.is_detached
        assert repo.head.commit.hexsha == original_sha
        assert self.branch not in repo.heads
        assert sentinel.read_text(encoding="utf-8") == "keep me"
