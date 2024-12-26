import json
import logging
import pathlib
import uuid
from functools import wraps

import git
import gitlab
import gitlab.exceptions
from cachetools import TTLCache
from cachetools import cached
from django.conf import settings
from gitlab.v4.objects.projects import ProjectManager as Gitlab_ProjectManager

from speleodb.common.models import Option
from speleodb.git_engine.core import GitRepo
from speleodb.utils.lazy_string import LazyString
from speleodb.utils.metaclasses import SingletonMetaClass

GIT_COMMITTER = git.Actor("SpeleoDB", "contact@speleodb.com")

logger = logging.getLogger(__name__)


class GitlabError(Exception):
    pass


def check_initialized(func):
    @wraps(func)
    def _impl(self, *args, **kwargs):
        if not self._is_initialized:
            try:
                self._initialize()
            except Exception as e:
                raise GitlabError from e

        try:
            return func(self, *args, **kwargs)
        except GitlabError:
            # Force re-auth just in case
            self._is_initialized = False

    return _impl


class _GitlabManager(metaclass=SingletonMetaClass):
    FIRST_COMMIT_NAME = "[Automated] Project Creation"

    def __init__(self):
        self._is_initialized = False
        self._is_error = False

    def _initialize(self) -> None:
        # Allow Starting SpeleoDB without GITLAB Options to be defined.
        self._gitlab_instance = LazyString(
            lambda: Option.get_or_empty(name="GITLAB_HOST_URL")
        )
        self._gitlab_token = LazyString(
            lambda: Option.get_or_empty(name="GITLAB_TOKEN")
        )
        self._gitlab_group_id = LazyString(
            lambda: Option.get_or_empty(name="GITLAB_GROUP_ID")
        )
        self._gitlab_group_name = LazyString(
            lambda: Option.get_or_empty(name="GITLAB_GROUP_NAME")
        )

        self._gl = gitlab.Gitlab(
            f"https://{self._gitlab_instance}/", private_token=self._gitlab_token
        )

        try:
            self._gl.auth()
        except gitlab.exceptions.GitlabAuthenticationError:
            self._gl = None

        if settings.DEBUG_GITLAB and self._gl:
            self._gl.enable_debug()

    @check_initialized
    def create_or_clone_project(self, project_id: uuid.UUID) -> pathlib.Path | None:
        if self._gl is None:
            return None

        project_dir = settings.DJANGO_GIT_PROJECTS_DIR / str(project_id)
        git_url = f"https://oauth2:{self._gitlab_token}@{self._gitlab_instance}/{self._gitlab_group_name}/{project_id}.git"

        try:
            # try to create the repository in Gitlab
            _ = self._gl.projects.create(
                {"name": str(project_id), "namespace_id": str(self._gitlab_group_id)}
            )
            project_dir.mkdir(exist_ok=True, parents=True)

            git_repo = git.Repo.init(project_dir)
            origin = git_repo.create_remote("origin", url=git_url)
            origin.fetch()
            assert origin.exists()

            # Create an initial empty commit
            git_repo.index.commit(
                _GitlabManager.FIRST_COMMIT_NAME,
                author=GIT_COMMITTER,
                committer=GIT_COMMITTER,
            )
            git_repo.git.push(
                "--set-upstream", origin.name, settings.DJANGO_GIT_BRANCH_NAME
            )

        except gitlab.exceptions.GitlabCreateError:
            # The repository already exists in Gitlab - git clone instead

            # Ensure the parent directory exists
            project_dir.parent.mkdir(exist_ok=True, parents=True)
            git_repo = git.Repo.clone_from(url=git_url, to_path=project_dir)

        return GitRepo.from_repo(repo=git_repo)

    # cache data for no longer than ten minutes
    @cached(cache=TTLCache(maxsize=100, ttl=600))
    @check_initialized
    def _get_project(self, project_id: uuid.UUID) -> Gitlab_ProjectManager:
        if self._gl is None:
            return None

        try:
            return self._gl.projects.get(f"{self._gitlab_group_name}/{project_id}")
        except gitlab.exceptions.GitlabHttpError:
            # Communication Problem
            return None

    @check_initialized
    def get_commit_history(self, project_id: uuid.UUID) -> list | None:
        if self._gl is None:
            return None

        try:
            try:
                project = self._get_project(project_id)
            except gitlab.exceptions.GitlabGetError:
                return "ERROR: Project does not exist in Gitlab."

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


GitlabManager = _GitlabManager()
