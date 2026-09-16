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

from speleodb.common.management.commands import check_gitlab
from speleodb.testing.gitlab_audit import creation_allocation
from speleodb.testing.gitlab_audit import get_ledger
from speleodb.testing.gitlab_lifecycle import assert_remote_deleted
from speleodb.testing.gitlab_lifecycle import cleanup_remote_on_exit
from speleodb.testing.gitlab_pool import get_pool

if TYPE_CHECKING:
    from django.conf import LazySettings

pytestmark = pytest.mark.skip_if_lighttest


def test_check_gitlab_verifies_real_identity_and_project_write(
    settings: LazySettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = StringIO()
    project_uuid = uuid4()
    monkeypatch.setattr(check_gitlab, "uuid4", lambda: project_uuid)
    project_path: str = f"ci-preflight-{project_uuid.hex}"
    with (
        cleanup_remote_on_exit(
            get_pool().client, f"{settings.GITLAB_GROUP_NAME}/{project_path}"
        ),
        creation_allocation("write-check", settings.GITLAB_GROUP_ID, project_path),
    ):
        call_command("check_gitlab", stdout=output)
    allocation = next(
        row
        for row in get_ledger().summary()["allocations"]
        if row["name"] == "write-check"
    )
    assert_remote_deleted(get_pool().client, int(allocation["project_id"]))
    text: str = output.getvalue()
    assert f"host={settings.GITLAB_HOST_URL}" in text
    assert f"group={settings.GITLAB_GROUP_NAME}" in text
    assert "GitLab authenticated write check passed." in text
    token_was_printed: bool = settings.GITLAB_TOKEN in text
    assert not token_was_printed


def test_check_gitlab_read_only_never_creates_a_repository(
    settings: LazySettings,
) -> None:
    output = StringIO()
    before: int = get_ledger().summary()["creation_requests"]
    call_command("check_gitlab", "--read-only", stdout=output)
    text: str = output.getvalue()
    assert f"group={settings.GITLAB_GROUP_NAME}" in text
    assert "GitLab authenticated read-only check passed." in text
    assert get_ledger().summary()["creation_requests"] == before


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
