# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from functools import cache
from functools import lru_cache
from functools import wraps
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Self
from typing import TypeVar
from urllib.parse import quote

import gitlab
import gitlab.exceptions
from django.conf import settings

from speleodb.git_engine.client import GitlabClient
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.operations import retry_git_operation
from speleodb.utils.metaclasses import SingletonMetaClass

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from gitlab.v4.objects.projects import Project as GL_Project

    from speleodb.surveys.models import Project


logger = logging.getLogger(__name__)


class GitlabError(Exception):
    pass


RT = TypeVar("RT")


def check_initialized[RT](func: Callable[..., RT]) -> Callable[..., RT]:
    @wraps(func)
    def _impl(self: GitlabManagerCls, *args: Any, **kwargs: Any) -> RT:
        if self._gl is None:
            try:
                self._initialize()
            except Exception as e:
                raise GitlabError from e

        try:
            if self._gl is None:
                raise GitlabError("`_gl` is None. Not authenticated with Gitlab.")  # noqa: TRY301
            return func(self, *args, **kwargs)

        except GitlabError:
            # Force re-auth just in case
            self._gl = None
            raise

    return _impl


@dataclass(frozen=True)
class GitlabCredentials:
    instance: str
    token: str
    group_id: str
    group_name: str

    def project_url(self, project_id: UUID) -> str:
        return (
            f"{settings.GITLAB_HTTP_PROTOCOL}://oauth2:{quote(self.token, safe='')}"
            f"@{self.instance}/{self.group_name}/{project_id}.git"
        )

    @classmethod
    @cache
    def get(cls) -> Self:
        return cls(
            instance=settings.GITLAB_HOST_URL,
            token=settings.GITLAB_TOKEN,
            group_id=settings.GITLAB_GROUP_ID,
            group_name=settings.GITLAB_GROUP_NAME,
        )


class GitlabManagerCls(metaclass=SingletonMetaClass):
    _gl: gitlab.Gitlab | None = None

    def __init__(self) -> None:
        self._is_error = False

    def _initialize(self) -> None:
        """Allow Starting SpeleoDB without GITLAB Options to be defined."""

        gitlab_creds = GitlabCredentials.get()

        client = GitlabClient(
            f"{settings.GITLAB_HTTP_PROTOCOL}://{gitlab_creds.instance}",
            private_token=gitlab_creds.token,
            keep_base_url=settings.GITLAB_HTTP_PROTOCOL == "http",
        )

        self._gl = None
        self._get_project.cache_clear()
        try:
            client.auth()
        except Exception:
            client.session.close()
            raise

        self._gl = client
        if settings.DEBUG_GITLAB:
            client.enable_debug()

    @check_initialized
    def create_project(self, project: Project) -> None:
        """Trying to create the repository in Gitlab."""
        if self._gl is None:
            raise ValueError("Gitlab API has not been initialized")

        gitlab_creds = GitlabCredentials.get()

        self._gl.projects.create(
            {"name": str(project.id), "namespace_id": str(gitlab_creds.group_id)},
            retry_transient_errors=True,
        )

    @check_initialized
    def create_or_clone_project(
        self,
        project: Project,
        base_dir: str | Path | None = None,
    ) -> GitRepo | None:
        gitlab_creds = GitlabCredentials.get()

        git_repo_base_dir = (
            Path(base_dir)
            if base_dir is not None
            else Path(settings.DJANGO_GIT_PROJECTS_DIR)
        )

        project_dir = git_repo_base_dir / str(project.id)

        shutil.rmtree(project_dir, ignore_errors=True)

        project_dir.parent.mkdir(exist_ok=True, parents=True)
        git_url = gitlab_creds.project_url(project.id)

        git_repo: GitRepo
        try:
            # try to create the repository in Gitlab
            self.create_project(project)
        except gitlab.exceptions.GitlabCreateError as create_error:
            # GitLab reports duplicate paths as 400 or 409, but these codes
            # can also describe other errors. Confirm the repository exists
            # before falling back to clone; never mask a failed create with
            # repeated clones of a nonexistent repository.
            if create_error.response_code not in {
                HTTPStatus.BAD_REQUEST,
                HTTPStatus.CONFLICT,
            }:
                raise
            if self._gl is None:
                raise ValueError(
                    "Gitlab API has not been initialized"
                ) from create_error
            try:
                self._gl.projects.get(
                    f"{gitlab_creds.group_name}/{project.id}",
                )
            except gitlab.exceptions.GitlabGetError as lookup_error:
                if lookup_error.response_code == HTTPStatus.NOT_FOUND:
                    raise create_error from None
                raise

            git_repo = GitRepo.clone_from(url=git_url, to_path=project_dir)
            if not git_repo.head.is_valid():
                if git_repo.remotes.origin.refs:
                    # An unset/stale remote HEAD does not imply an empty remote.
                    git_repo.checkout_default_branch_and_pull()
                else:
                    git_repo.publish_first_commit()
        else:
            git_repo = GitRepo.init(project_dir)

            retry_git_operation(
                git_repo.create_remote,
                "origin",
                url=git_url,
                remote_url=git_url,
                action="configure origin for",
            )

            # Create an initial empty commit
            git_repo.publish_first_commit()

        return git_repo

    @lru_cache(maxsize=256)  # noqa: B019
    @check_initialized
    def _get_project(self, project: Project) -> GL_Project | None:
        if self._gl is None:
            raise ValueError("Gitlab API has not been initialized")

        gitlab_creds = GitlabCredentials.get()
        # Cache only successful lookups. A 404 can be temporary after creation;
        # raised exceptions are deliberately not cached by lru_cache.
        return self._gl.projects.get(f"{gitlab_creds.group_name}/{project.id}")

    @check_initialized
    def get_commit_history(self, project: Project) -> list[dict[str, Any]] | None:
        try:
            gl_project = self._get_project(project)

            if gl_project is None:
                return None

            commits = gl_project.commits.list(get_all=True, all=True)
            data = [json.loads(commit.to_json()) for commit in commits]

            # Removes traces of a download URL from gitlab
            for commit in data:
                del commit["web_url"]

        except (
            gitlab.exceptions.GitlabGetError,
            gitlab.exceptions.GitlabListError,
        ) as error:
            if error.response_code == HTTPStatus.NOT_FOUND:
                self._get_project.cache_clear()
                return None
            raise

        return data

    @check_initialized
    def get_last_commit_hash(self, project: Project) -> str | None:
        try:
            gl_project = self._get_project(project)

            if gl_project is None:
                return None

            branch = gl_project.branches.get(settings.DJANGO_GIT_BRANCH_NAME)

            # Get the current hash of the branch
            return branch.commit["id"]  # type: ignore[no-any-return]

        except gitlab.exceptions.GitlabGetError as error:
            if error.response_code == HTTPStatus.NOT_FOUND:
                self._get_project.cache_clear()
                return None
            raise


GitlabManager: GitlabManagerCls = GitlabManagerCls()
