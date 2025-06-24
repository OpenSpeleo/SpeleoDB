# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Self
from typing import TypeVar

import gitlab
import gitlab.exceptions
from cachetools import TTLCache
from cachetools import cached
from django.conf import settings

from speleodb.common.models import Option
from speleodb.git_engine.core import GitRepo
from speleodb.utils.metaclasses import SingletonMetaClass

if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable

    from gitlab.v4.objects.projects import Project

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

    @classmethod
    @cached(cache=TTLCache(maxsize=1, ttl=30))  # 60 secs cache
    def get(cls) -> Self:
        return cls(
            instance=Option.get_or_empty(name="GITLAB_HOST_URL"),
            token=Option.get_or_empty(name="GITLAB_TOKEN"),
            group_id=Option.get_or_empty(name="GITLAB_GROUP_ID"),
            group_name=Option.get_or_empty(name="GITLAB_GROUP_NAME"),
        )


class GitlabManagerCls(metaclass=SingletonMetaClass):
    _gl: gitlab.Gitlab | None = None

    def __init__(self) -> None:
        self._is_error = False

    def _initialize(self) -> None:
        """Allow Starting SpeleoDB without GITLAB Options to be defined."""

        gitlab_creds = GitlabCredentials.get()

        self._gl = gitlab.Gitlab(
            f"https://{gitlab_creds.instance}/",
            private_token=gitlab_creds.token,
        )

        try:
            self._gl.auth()
        except gitlab.exceptions.GitlabAuthenticationError:
            self._gl = None

        if settings.DEBUG_GITLAB and self._gl:
            self._gl.enable_debug()

    @check_initialized
    def create_project(self, project_id: uuid.UUID) -> None:
        """Trying to create the repository in Gitlab."""
        if self._gl is None:
            raise ValueError("Gitlab API has not been initialized")

        gitlab_creds = GitlabCredentials.get()

        self._gl.projects.create(
            {"name": str(project_id), "namespace_id": str(gitlab_creds.group_id)}
        )

    @check_initialized
    def create_or_clone_project(self, project_id: uuid.UUID) -> GitRepo | None:
        gitlab_creds = GitlabCredentials.get()

        project_dir = Path(settings.DJANGO_GIT_PROJECTS_DIR / str(project_id))
        project_dir.parent.mkdir(exist_ok=True, parents=True)
        git_url = f"https://oauth2:{gitlab_creds.token}@{gitlab_creds.instance}/{gitlab_creds.group_name}/{project_id}.git"

        try:
            # try to create the repository in Gitlab
            self.create_project(project_id=project_id)

            git_repo = GitRepo.init(project_dir)
            origin = git_repo.create_remote("origin", url=git_url)
            origin.fetch()
            assert origin.exists()

            # Create an initial empty commit
            git_repo.publish_first_commit()

            return git_repo

        except gitlab.exceptions.GitlabCreateError:
            # The repository already exists in Gitlab - git clone instead
            return GitRepo.clone_from(url=git_url, to_path=project_dir)

    # cache data for no longer than ten minutes
    @cached(cache=TTLCache(maxsize=100, ttl=600))
    @check_initialized
    def _get_project(self, project_id: uuid.UUID) -> Project | None:
        if self._gl is None:
            raise ValueError("Gitlab API has not been initialized")

        gitlab_creds = GitlabCredentials.get()
        try:
            return self._gl.projects.get(f"{gitlab_creds.group_name}/{project_id}")
        except gitlab.exceptions.GitlabHttpError:
            # Communication Problem
            return None

    @check_initialized
    def get_commit_history(self, project_id: uuid.UUID) -> list[dict[str, Any]] | None:
        try:
            try:
                project = self._get_project(project_id)
            except gitlab.exceptions.GitlabGetError as e:
                raise RuntimeError from e

            if project is None:
                return None

            commits = project.commits.list(get_all=True, all=True)
            data = [json.loads(commit.to_json()) for commit in commits]

            # Removes traces of a download URL from gitlab
            for commit in data:
                del commit["web_url"]

        except gitlab.exceptions.GitlabHttpError:
            return None

        return data

    def get_last_commit_hash(self, project_id: uuid.UUID) -> str | None:
        try:
            try:
                project = self._get_project(project_id)
            except gitlab.exceptions.GitlabGetError as e:
                raise RuntimeError from e

            if project is None:
                return None

            branch = project.branches.get(settings.DJANGO_GIT_BRANCH_NAME)

            # Get the current hash of the branch
            return branch.commit["id"]  # type: ignore[no-any-return]

        except gitlab.exceptions.GitlabHttpError:
            return None


GitlabManager: GitlabManagerCls = GitlabManagerCls()
