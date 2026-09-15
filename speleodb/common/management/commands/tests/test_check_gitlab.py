from __future__ import annotations

from http import HTTPStatus
from io import StringIO
from typing import TYPE_CHECKING
from uuid import uuid4

import gitlab.exceptions
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

if TYPE_CHECKING:
    from django.conf import LazySettings


def test_check_gitlab_verifies_real_identity_and_project_write(
    settings: LazySettings,
) -> None:
    output = StringIO()
    call_command("check_gitlab", stdout=output)
    text: str = output.getvalue()
    assert f"host={settings.GITLAB_HOST_URL}" in text
    assert f"group={settings.GITLAB_GROUP_NAME}" in text
    assert "GitLab authenticated write check passed." in text
    token_was_printed: bool = settings.GITLAB_TOKEN in text
    assert not token_was_printed


def test_check_gitlab_rejects_actual_invalid_token() -> None:
    with (
        override_settings(GITLAB_TOKEN=f"invalid-{uuid4().hex}"),
        pytest.raises(gitlab.exceptions.GitlabAuthenticationError) as raised,
    ):
        call_command("check_gitlab", stdout=StringIO())
    assert raised.value.response_code == HTTPStatus.UNAUTHORIZED


def test_check_gitlab_rejects_mismatched_group_before_writing() -> None:
    with (
        override_settings(GITLAB_GROUP_NAME=f"wrong-{uuid4().hex}"),
        pytest.raises(CommandError, match="identify different groups"),
    ):
        call_command("check_gitlab", stdout=StringIO())
