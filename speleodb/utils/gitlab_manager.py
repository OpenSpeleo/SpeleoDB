import json
import pathlib

import git
import gitlab
import gitlab.exceptions
from django.conf import settings
from gitlab.v4.objects.projects import ProjectManager

from speleodb.common.models import Option
from speleodb.utils.metaclasses import SingletonMetaClass


class _GitlabManager(metaclass=SingletonMetaClass):
    def __init__(self):
        self._gitlab_instance = Option.get_or_empty(name="GITLAB_HOST_URL").value
        self._gitlab_token = Option.get_or_empty(name="GITLAB_TOKEN").value
        self._gitlab_group_id = Option.get_or_empty(name="GITLAB_GROUP_ID").value
        self._gitlab_group_name = Option.get_or_empty(name="GITLAB_GROUP_NAME").value

        self._gl = gitlab.Gitlab(
            f"https://{self._gitlab_instance}/", private_token=self._gitlab_token
        )

        try:
            self._gl.auth()
        except gitlab.exceptions.GitlabAuthenticationError:
            self._gl = None

        if settings.DEBUG and self._gl:
            self._gl.enable_debug()

    def create_project(self, project_id) -> pathlib.Path:
        if self._gl is None:
            return None

        try:
            try:
                _ = self._gl.projects.create(
                    {"name": str(project_id), "namespace_id": self._gitlab_group_id}
                )
            # except gitlab.exceptions.InvalidGitRepositoryError:
            except gitlab.exceptions.GitlabCreateError as e:
                # The repository already exists in gitlab - skip in debug
                if not settings.DEBUG or "has already been taken" not in str(e):
                    raise

            project_dir = settings.GIT_PROJECTS_DIR / str(project_id)
            project_dir.mkdir(exist_ok=True, parents=True)

            git_repo = git.Repo.init(project_dir)

            origin = git_repo.create_remote(
                "origin",
                url=f"https://oauth2:{self._gitlab_token}@{self._gitlab_instance}/{self._gitlab_group_name}/{project_id}.git",
            )
            assert origin.exists()

        except gitlab.exceptions.GitlabCreateError:
            return None

        return project_dir

    def _get_project(self, project_id) -> ProjectManager:
        if self._gl is None:
            return None

        try:
            return self._gl.projects.get(f"{self._gitlab_group_name}/{project_id}")
        except gitlab.exceptions.GitlabHttpError:
            # Communication Problem
            return None

    def get_commit_history(self, project_id, hide_dl_url=True):
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
            if hide_dl_url:
                for commit in data:
                    del commit["web_url"]

        except gitlab.exceptions.GitlabHttpError:
            return None

        return data


GitlabManager = _GitlabManager()
