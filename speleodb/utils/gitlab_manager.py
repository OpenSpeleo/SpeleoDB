import json

import git
import gitlab
import gitlab.exceptions
from django.conf import settings

from speleodb.common.models import Option
from speleodb.utils.metaclasses import LazySingletonMetaClass


class _GitlabManager(metaclass=LazySingletonMetaClass):
    def __init__(self):
        self._gitlab_instance = Option.objects.get(name="GITLAB_HOST_URL").value
        self._gitlab_token = Option.objects.get(name="GITLAB_TOKEN").value
        self._gitlab_group_id = Option.objects.get(name="GITLAB_GROUP_ID").value
        self._gitlab_group_name = Option.objects.get(name="GITLAB_GROUP_NAME").value

        self._gl = gitlab.Gitlab(
            f"https://{self._gitlab_instance}/", private_token=self._gitlab_token
        )

        try:
            self._gl.auth()
        except gitlab.exceptions.GitlabAuthenticationError:
            self._gl = None

        if settings.DEBUG:
            self._gl.enable_debug()

    def create_project(self, project_id):
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

    def get_project(self, project_id):
        try:
            return self._gl.projects.get(f"{self._gitlab_group_name}/{project_id}")
        except gitlab.exceptions.GitlabHttpError:
            return None

    def get_commit_history(self, project_id, hide_dl_url=True):
        try:
            project = self.get_project(project_id)
            commits = project.commits.list(get_all=True, all=True)
            data = [json.loads(commit.to_json()) for commit in commits]
            if hide_dl_url:
                for commit in data:
                    del commit["web_url"]
        except gitlab.exceptions.GitlabHttpError:
            return None

        return data


GitlabManager = _GitlabManager()
