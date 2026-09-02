# -*- coding: utf-8 -*-

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager


class CreateOrCloneProjectTests(TestCase):
    def test_new_project_does_not_fetch_empty_remote(self) -> None:
        project = MagicMock()
        project.id = uuid.uuid4()
        git_repo = MagicMock(spec=GitRepo)
        origin = MagicMock()
        git_repo.create_remote.return_value = origin
        credentials = GitlabCredentials(
            instance="gitlab.example",
            token=uuid.uuid4().hex,
            group_id="1",
            group_name="test-group",
        )

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(GitlabManager, "_gl", MagicMock()),
            patch.object(GitlabCredentials, "get", return_value=credentials),
            patch.object(GitlabManager, "create_project") as create_project,
            patch.object(GitRepo, "init", return_value=git_repo),
        ):
            result = GitlabManager.create_or_clone_project(
                project,
                base_dir=Path(temp_dir),
            )

        assert result is git_repo
        create_project.assert_called_once_with(project)
        git_repo.create_remote.assert_called_once()
        origin.fetch.assert_not_called()
        git_repo.publish_first_commit.assert_called_once_with()
