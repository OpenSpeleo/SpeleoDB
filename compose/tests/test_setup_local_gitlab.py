# ruff: noqa: S105, S106

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from typing import Any
from unittest.mock import MagicMock

import gitlab
from gitlab.const import AccessLevel

from compose.setup_local_gitlab import PythonGitLabClient
from compose.setup_local_gitlab import initialize_env_file
from compose.setup_local_gitlab import provision_gitlab
from compose.setup_local_gitlab import read_env_file
from compose.setup_local_gitlab import update_env_file

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


PRIVATE_ENV_MODE = 0o600


def test_private_env_is_copied_from_template_once(tmp_path: Path) -> None:
    env_template = tmp_path / ".env.dist"
    env_file = tmp_path / ".env"
    env_template.write_text("TEMPLATE=value\n", encoding="utf-8")

    assert initialize_env_file(env_file, env_template) is True
    assert env_file.read_text(encoding="utf-8") == "TEMPLATE=value\n"
    assert env_file.stat().st_mode & 0o777 == PRIVATE_ENV_MODE

    env_file.write_text("DEVELOPER=preserved\n", encoding="utf-8")
    assert initialize_env_file(env_file, env_template) is False
    assert env_file.read_text(encoding="utf-8") == "DEVELOPER=preserved\n"
    assert env_file.stat().st_mode & 0o777 == PRIVATE_ENV_MODE


def test_python_gitlab_client_uses_resource_managers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group_access_tokens = MagicMock()
    group_access_tokens.list.return_value = [
        SimpleNamespace(
            id=11,
            name="speleodb-local-development",
            expires_at=None,
        )
    ]
    group_access_tokens.create.return_value = SimpleNamespace(
        id=12,
        token="created-group-token",
    )
    group = SimpleNamespace(
        id=7,
        name="speleodb",
        access_tokens=group_access_tokens,
    )
    admin = MagicMock()
    admin.groups.get.return_value = group
    admin.groups.create.return_value = group
    group_token_client = MagicMock()
    gitlab_factory = MagicMock(side_effect=[admin, group_token_client])
    monkeypatch.setattr(gitlab, "Gitlab", gitlab_factory)

    client = PythonGitLabClient(
        "http://localhost:9080/",
        "bootstrap-token",
    )

    assert client.find_group("speleodb") == {"id": 7, "name": "speleodb"}
    assert client.create_group("speleodb") == {"id": 7, "name": "speleodb"}
    assert client.token_can_access_group("7", "existing-group-token") is True
    assert client.list_group_tokens("7") == [
        {
            "id": 11,
            "name": "speleodb-local-development",
            "active": True,
            "expires_at": None,
        }
    ]
    client.revoke_group_token("7", "11")
    assert client.create_group_token("7", "speleodb-local-development") == {
        "id": 12,
        "token": "created-group-token",
    }

    gitlab_factory.assert_any_call(
        "http://localhost:9080",
        private_token="bootstrap-token",
        timeout=15,
        retry_transient_errors=True,
        keep_base_url=True,
    )
    group_token_client.groups.get.assert_called_once_with("7")
    group_access_tokens.list.assert_called_once_with(iterator=True, state="active")
    group_access_tokens.delete.assert_called_once_with("11")
    group_access_tokens.create.assert_called_once_with(
        {
            "name": "speleodb-local-development",
            "scopes": ["api", "read_repository", "write_repository"],
            "access_level": AccessLevel.OWNER,
            "expires_at": None,
        }
    )


class FakeGitLabClient:
    def __init__(
        self,
        *,
        group: dict[str, Any] | None,
        token_valid: bool,
        group_tokens: list[dict[str, Any]] | None = None,
    ) -> None:
        self.group = group
        self.token_valid = token_valid
        self.group_tokens = group_tokens or []
        self.created_groups: list[str] = []
        self.revoked_tokens: list[tuple[str, str]] = []
        self.created_tokens: list[tuple[str, str]] = []

    def find_group(self, group_name: str) -> dict[str, Any] | None:
        return self.group

    def create_group(self, group_name: str) -> dict[str, Any]:
        self.created_groups.append(group_name)
        self.group = {"id": 42, "name": group_name}
        return self.group

    def token_can_access_group(self, group_id: str, token: str) -> bool:
        return self.token_valid

    def list_group_tokens(self, group_id: str) -> list[dict[str, Any]]:
        return self.group_tokens

    def revoke_group_token(self, group_id: str, token_id: str) -> None:
        self.revoked_tokens.append((group_id, token_id))

    def create_group_token(self, group_id: str, token_name: str) -> dict[str, Any]:
        self.created_tokens.append((group_id, token_name))
        return {"id": 99, "token": "new-group-token"}


def test_existing_group_and_valid_token_are_reused() -> None:
    client = FakeGitLabClient(
        group={"id": 7},
        token_valid=True,
        group_tokens=[
            {
                "id": 10,
                "name": "speleodb-local-development",
                "active": True,
                "expires_at": None,
            }
        ],
    )

    result = provision_gitlab(
        client,
        group_name="speleodb",
        token_name="speleodb-local-development",
        current_token="existing-token",
    )

    assert result.group_id == "7"
    assert result.group_token == "existing-token"
    assert result.group_created is False
    assert result.token_created is False
    assert client.created_groups == []
    assert client.created_tokens == []
    assert client.revoked_tokens == []


def test_existing_expiring_token_is_replaced() -> None:
    client = FakeGitLabClient(
        group={"id": 7},
        token_valid=True,
        group_tokens=[
            {
                "id": 10,
                "name": "speleodb-local-development",
                "active": True,
                "expires_at": "2027-07-17",
            }
        ],
    )

    result = provision_gitlab(
        client,
        group_name="speleodb",
        token_name="speleodb-local-development",
        current_token="expiring-token",
    )

    assert result.group_token == "new-group-token"
    assert result.token_created is True
    assert client.revoked_tokens == [("7", "10")]
    assert client.created_tokens == [("7", "speleodb-local-development")]


def test_missing_group_and_token_are_created() -> None:
    client = FakeGitLabClient(group=None, token_valid=False)

    result = provision_gitlab(
        client,
        group_name="speleodb",
        token_name="speleodb-local-development",
        current_token=None,
    )

    assert result.group_id == "42"
    assert result.group_token == "new-group-token"
    assert result.group_created is True
    assert result.token_created is True
    assert client.created_groups == ["speleodb"]
    assert client.created_tokens == [("42", "speleodb-local-development")]


def test_invalid_named_token_is_revoked_before_replacement() -> None:
    client = FakeGitLabClient(
        group={"id": 7},
        token_valid=False,
        group_tokens=[
            {"id": 12, "name": "unrelated", "active": True},
            {"id": 13, "name": "speleodb-local-development", "active": True},
        ],
    )

    result = provision_gitlab(
        client,
        group_name="speleodb",
        token_name="speleodb-local-development",
        current_token="expired-token",
    )

    assert result.group_token == "new-group-token"
    assert client.revoked_tokens == [("7", "13")]
    assert client.created_tokens == [("7", "speleodb-local-development")]


def test_private_env_update_preserves_user_values_and_is_idempotent(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Developer overrides\nCUSTOM=value\nGITLAB_TOKEN=old-token\n"
        "GITLAB_TOKEN=duplicate-old-token\n",
        encoding="utf-8",
    )
    values = {
        "GITLAB_GROUP_ID": "42",
        "GITLAB_TOKEN": "new-token",
        "AWS_STORAGE_BUCKET_NAME": "speleodb-user-artifacts-dev",
    }

    assert update_env_file(env_file, values) is True
    assert read_env_file(env_file) == {
        "CUSTOM": "value",
        **values,
    }
    assert env_file.read_text(encoding="utf-8").count("GITLAB_TOKEN=") == 1
    assert update_env_file(env_file, values) is False
    assert env_file.stat().st_mode & 0o777 == PRIVATE_ENV_MODE
