import contextlib
import json
import logging
import pathlib
import time
import uuid
from functools import wraps

import git
import gitlab
import gitlab.exceptions
from cachetools import TTLCache
from cachetools import cached
from django.conf import settings
from gitlab.v4.objects.projects import ProjectManager

from speleodb.common.models import Option
from speleodb.users.models import User
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


class GitRepo:
    def __init__(self, git_repo) -> None:
        if isinstance(git_repo, pathlib.Path):
            git_repo = git.Repo(git_repo)
        self._repo = git_repo

    def __fspath__(self):
        return self._repo.working_tree_dir

    @property
    def repo(self):
        return self._repo

    @property
    def path(self):
        return pathlib.Path(self)

    @property
    def commit_sha1(self):
        return self._repo.head.commit.hexsha

    @property
    def commit_sha1_short(self):
        return self.commit_sha1[:8]

    @property
    def commit_date(self):
        return time.gmtime(self._repo.head.commit.committed_date)

    def checkout_and_pull(self, branch: str = "master"):
        self.checkout_branch_or_commit(branch_name=branch)
        self.pull()

    def pull(self):
        origin = self._repo.remotes.origin
        origin.pull()

    def checkout_branch_or_commit(
        self, commit_sha1: str | None = None, branch_name: str | None = None
    ):
        if commit_sha1 and branch_name:
            raise ValueError(
                f"`{commit_sha1=}` and `{branch_name=}` can not be set simultaneously."
            )

        if commit_sha1 is None and branch_name is None:
            raise ValueError(
                f"`{commit_sha1=}` and `{branch_name=}` can not be both set to `None`."
            )

        try:
            self._repo.git.checkout(branch_name or commit_sha1)
        except git.exc.GitCommandError:
            if branch_name:
                self._repo.git.checkout("-b", branch_name)
            else:
                raise

        if branch_name:
            # Ensure we are at the top of the branch
            self.pull()

    def checkout_branch(self, branch_name: str):
        raise NotImplementedError

    def commit_and_push_project(self, message: str, user: User) -> str:
        # Add every file pending
        self._repo.index.add("*")

        # If there are modified files:
        if self._repo.is_dirty():
            author = git.Actor(user.name, user.email)

            commit = self._repo.index.commit(
                message, author=author, committer=GIT_COMMITTER
            )

            self._repo.git.push("--set-upstream", "origin", self._repo.active_branch)

            return commit.hexsha

        return None


class _GitlabManager(metaclass=SingletonMetaClass):
    __GITLAB_CACHE__ = TTLCache(maxsize=100, ttl=600)
    FIRST_COMMIT_NAME = "[Automated] Project Creation"

    def __init__(self):
        self._is_initialized = False
        self._is_error = False

    def _initialize(self):
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
    def create_or_clone_project(self, project_id: uuid.UUID) -> pathlib.Path:
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
            assert origin.exists()

            # Create an initial empty commit
            git_repo.index.commit(
                _GitlabManager.FIRST_COMMIT_NAME,
                author=GIT_COMMITTER,
                committer=GIT_COMMITTER,
            )
            git_repo.git.push("--set-upstream", "origin", "master")

        except gitlab.exceptions.GitlabCreateError:
            # The repository already exists in Gitlab - git clone instead

            # Ensure the parent directory exists
            project_dir.parent.mkdir(exist_ok=True, parents=True)
            git_repo = git.Repo.clone_from(git_url, project_dir)

        return GitRepo(git_repo=git_repo)

    # cache data for no longer than ten minutes
    @cached(cache=TTLCache(maxsize=100, ttl=600))
    @check_initialized
    def _get_project(self, project_id: uuid.UUID) -> ProjectManager:
        if self._gl is None:
            return None

        try:
            return self._gl.projects.get(f"{self._gitlab_group_name}/{project_id}")
        except gitlab.exceptions.GitlabHttpError:
            # Communication Problem
            return None

    @classmethod
    def void_project_gitlab_cache(cls, project_id: uuid.UUID):
        with contextlib.suppress(KeyError):
            del cls.__GITLAB_CACHE__[project_id]

    @cached(cache=__GITLAB_CACHE__, key=lambda self, project_id: project_id)
    @check_initialized
    def get_commit_history(self, project_id: uuid.UUID):
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
