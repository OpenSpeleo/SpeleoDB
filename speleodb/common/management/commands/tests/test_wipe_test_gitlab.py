"""Cleanup commands require one explicit confirmation and report remote failures."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from unittest.mock import patch

import gitlab.exceptions
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def gitlab_cleanup_client() -> Generator[MagicMock]:
    client: MagicMock = MagicMock()
    group: MagicMock = client.groups.get.return_value
    group.id = 1
    group.full_name = "test-group"
    group.web_url = "https://gitlab.invalid/test-group"
    project: MagicMock = MagicMock()
    project.id = 2
    project.name = "test-project"
    project.web_url = "https://gitlab.invalid/test-group/test-project"
    group.projects.list.return_value = [project]
    with (
        patch.dict(
            os.environ,
            {
                "GITLAB_GROUP_ID": "1",
                "GITLAB_GROUP_NAME": "test-group",
                "GITLAB_HOST_URL": "gitlab.invalid",
                "GITLAB_TOKEN": "test-token",
            },
        ),
        patch(
            "speleodb.common.management.commands.wipe_test_gitlab.load_dotenv",
            return_value=True,
        ),
        patch(
            "speleodb.common.management.commands.wipe_test_gitlab.GitlabClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.mark.parametrize("answer", ["", "N", "invalid", "yes"])
def test_invalid_or_empty_confirmation_cancels_once(
    gitlab_cleanup_client: MagicMock, answer: str
) -> None:
    with patch("builtins.input", side_effect=[answer, "Y"]) as prompt:
        call_command("wipe_test_gitlab", accept_danger=True)

    prompt.assert_called_once()
    gitlab_cleanup_client.groups.get.return_value.projects.list.assert_not_called()
    gitlab_cleanup_client.projects.get.assert_not_called()


def test_closed_input_cancels(gitlab_cleanup_client: MagicMock) -> None:
    with patch("builtins.input", side_effect=EOFError):
        call_command("wipe_test_gitlab", accept_danger=True)

    gitlab_cleanup_client.projects.get.assert_not_called()


def test_explicit_confirmation_deletes_once(gitlab_cleanup_client: MagicMock) -> None:
    with patch("builtins.input", return_value=" y ") as prompt:
        call_command("wipe_test_gitlab", accept_danger=True)

    prompt.assert_called_once()
    gitlab_cleanup_client.projects.get.assert_called_once_with(2)
    gitlab_cleanup_client.projects.get.return_value.delete.assert_called_once_with()


def test_dry_run_does_not_delete(gitlab_cleanup_client: MagicMock) -> None:
    call_command("wipe_test_gitlab", skip_user_confirmation=True)

    gitlab_cleanup_client.projects.get.assert_not_called()


def test_remote_failure_fails_the_command(gitlab_cleanup_client: MagicMock) -> None:
    gitlab_cleanup_client.projects.get.return_value.delete.side_effect = (
        gitlab.exceptions.GitlabDeleteError("upstream failed", response_code=503)
    )

    with pytest.raises(CommandError, match="cleanup could not finish"):
        call_command(
            "wipe_test_gitlab", accept_danger=True, skip_user_confirmation=True
        )

    gitlab_cleanup_client.projects.get.return_value.delete.assert_called_once_with()
