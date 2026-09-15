# -*- coding: utf-8 -*-

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

import git
import pytest
from django.conf import settings
from django.test import override_settings
from git.exc import GitCommandError

from speleodb.api.v2.tests.base_testcase import BaseProjectTestCaseMixin
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.exceptions import GitBaseError
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.processors.base import BaseFileProcessor


class GitCheckoutTests(TestCase):
    """Exercise branch selection and publication against local bare remotes."""

    def setUp(self) -> None:
        super().setUp()
        self.root: Path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.branch: str = "configured-main"
        self.enterContext(
            override_settings(
                DJANGO_GIT_BRANCH_NAME=self.branch,
                DJANGO_GIT_RETRY_BASE_DELAY_SECONDS=0.01,
                DJANGO_GIT_RETRY_MAX_DELAY_SECONDS=0.02,
            )
        )
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

        # A nonexistent fetch URL proves publication never fetches or pulls.
        # Git has a separate push URL, pointing at the real bare repository.
        repo.remotes.origin.set_url(str(self.root / "missing.git"))
        repo.remotes.origin.set_url(str(self.remote.git_dir), push=True)
        repo.publish_first_commit()

        self._assert_published_initial_commit(repo)

    def test_empty_clone_publishes_configured_initial_branch(self) -> None:
        repo: GitRepo = self._clone()
        assert not repo.head.is_valid()

        # A nonexistent fetch URL proves publication never fetches or pulls.
        # Git has a separate push URL, pointing at the real bare repository.
        repo.remotes.origin.set_url(str(self.root / "missing.git"))
        repo.remotes.origin.set_url(str(self.remote.git_dir), push=True)
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

        hook: Path = Path(self.remote.git_dir) / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho 'publication rejected' >&2\nexit 1\n")
        hook.chmod(0o755)

        with pytest.raises(GitBaseError, match="publication rejected"):
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

        repo.remotes.origin.set_url(str(self.root / "missing.git"))
        with pytest.raises(GitCommandError, match="would be overwritten"):
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

        repo.remotes.origin.set_url(str(self.root / "missing.git"))
        with pytest.raises(GitCommandError, match="would be overwritten"):
            repo.checkout_commit(original_sha)

        assert repo.active_branch.name == self.branch
        assert repo.head.commit.hexsha == latest_sha
        assert readme.read_text(encoding="utf-8") == "uncommitted changes"

    def test_existing_commit_checkout_does_not_contact_remote(self) -> None:
        original_sha: str = self._push_revision("first version")
        self._push_revision("latest version")
        repo: GitRepo = self._clone()

        repo.remotes.origin.set_url(str(self.root / "missing.git"))
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

    def test_pull_outage_preserves_existing_branch_and_files(self) -> None:
        original_sha: str = self._push_revision("first version")
        repo: GitRepo = self._clone()
        sentinel: Path = repo.path / "local-work.txt"
        sentinel.write_text("keep me", encoding="utf-8")

        repo.remotes.origin.set_url(str(self.root / "missing.git"))
        with pytest.raises(
            GitBaseError, match="does not appear to be a git repository"
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

        repo.remotes.origin.set_url(str(self.root / "missing.git"))
        with pytest.raises(
            GitBaseError, match="does not appear to be a git repository"
        ):
            repo.checkout_default_branch_and_pull()

        assert repo.head.is_detached
        assert repo.head.commit.hexsha == original_sha
        assert self.branch not in repo.heads
        assert sentinel.read_text(encoding="utf-8") == "keep me"


@pytest.mark.skip_if_lighttest
class GitDownloadCheckoutTests(BaseProjectTestCaseMixin):
    """Download through the actual project property and configured GitLab."""

    def setUp(self) -> None:
        super().setUp()
        self.root: Path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.repo: GitRepo = self.project.git_repo
        self.addCleanup(self.repo.close)
        self.seed: GitRepo = GitRepo.clone_from(
            GitlabCredentials.get().project_url(self.project.id),
            self.root / "seed",
            branch=settings.DJANGO_GIT_BRANCH_NAME,
        )
        self.addCleanup(self.seed.close)
        self.original_sha: str = self._push_revision("first version")
        self.repo.checkout_commit(self.original_sha)
        self.latest_sha: str = self._push_revision("latest version")
        self.processor: BaseFileProcessor = BaseFileProcessor(self.project)
        self.processor.TARGET_SAVE_FILENAME = "README.txt"
        self.target: Path = self.root / "download.txt"
        self.invalid_origin: str = str(self.root / "missing.git")
        self.repo.remotes.origin.set_url(self.invalid_origin)

    def _push_revision(self, content: str) -> str:
        (self.seed.path / "README.txt").write_text(content, encoding="utf-8")
        result: str | None = self.seed.commit_and_push_project(
            message=content, author_name=self.user.name, author_email=self.user.email
        )
        assert result is not None
        return result

    def test_latest_download_restores_default_branch_and_pulls_updates(self) -> None:
        filename: str = self.processor.get_filename_for_download(self.target)

        assert filename == self.target.name
        assert self.target.read_text(encoding="utf-8") == "latest version"
        assert self.repo.active_branch.name == settings.DJANGO_GIT_BRANCH_NAME
        assert self.repo.head.commit.hexsha == self.latest_sha
        assert self.repo.remotes.origin.url == GitlabCredentials.get().project_url(
            self.project.id
        )

    def test_commit_download_fetches_missing_objects_without_moving_head(self) -> None:
        filename: str = self.processor.get_filename_for_download(
            self.target, hexsha=self.latest_sha
        )

        assert filename == self.target.name
        assert self.target.read_text(encoding="utf-8") == "latest version"
        assert self.repo.head.is_detached
        assert self.repo.head.commit.hexsha == self.original_sha
        assert (self.repo.path / "README.txt").read_text(encoding="utf-8") == (
            "first version"
        )
        assert self.repo.remotes.origin.url == GitlabCredentials.get().project_url(
            self.project.id
        )

        # A cached commit can be downloaded with an unreachable remote. The
        # unchanged origin also proves no repair was attempted on this path.
        self.repo.remotes.origin.set_url(self.invalid_origin)
        self.processor.get_filename_for_download(self.target, hexsha=self.latest_sha)

        assert self.target.read_text(encoding="utf-8") == "latest version"
        assert self.repo.remotes.origin.url == self.invalid_origin
        assert self.repo.head.is_detached
        assert self.repo.head.commit.hexsha == self.original_sha
