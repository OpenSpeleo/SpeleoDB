"""Check setup helpers and authenticated access through the real GitLab API."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

import gitlab.exceptions
import pytest
from django.conf import settings

from compose.setup_local_gitlab import PythonGitLabClient
from compose.setup_local_gitlab import initialize_env_file
from compose.setup_local_gitlab import provision_gitlab
from compose.setup_local_gitlab import read_env_file
from compose.setup_local_gitlab import update_env_file

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from requests import Response

PRIVATE_ENV_MODE = 0o600
LOCAL_GITLAB = pytest.mark.skipif(
    settings.GITLAB_HOST_URL not in {"localhost:9080", "gitlab:9080"},
    reason="Local infrastructure provisioning applies to the local GitLab service",
)


@pytest.fixture
def setup_client() -> Generator[PythonGitLabClient]:
    """Require the same authenticated namespace as the integration suite."""
    client = PythonGitLabClient(
        f"{settings.GITLAB_HTTP_PROTOCOL}://{settings.GITLAB_HOST_URL}",
        settings.GITLAB_TOKEN,
    )
    try:
        client.admin.auth()
        assert client.admin.user is not None
        group = client.admin.groups.get(str(settings.GITLAB_GROUP_ID))
        assert group.full_path == settings.GITLAB_GROUP_NAME
        yield client
    finally:
        client.admin.session.close()


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        (
            {
                "GITLAB_SETUP_URL": "http://gitlab:9080",
                "AWS_S3_BROWSER_ENDPOINT_URL": "http://localhost:9000",
            },
            ["http://gitlab:9080", "localhost:9000/dev-bucket"],
        ),
        (
            {
                "AWS_S3_BROWSER_ENDPOINT_URL": "http://localhost:9000",
                "AWS_S3_CUSTOM_DOMAIN": "rustfs:9000/dev-bucket",
            },
            ["http://localhost:9080", "localhost:9000/dev-bucket"],
        ),
        ({}, ["http://localhost:9080", "rustfs:9000/dev-bucket"]),
    ],
)
def test_setup_resolves_internal_and_browser_addresses(
    environment: dict[str, str], expected: list[str]
) -> None:
    child_environment: dict[str, str] = os.environ.copy()
    for name in (
        "GITLAB_SETUP_URL",
        "AWS_S3_BROWSER_ENDPOINT_URL",
        "AWS_S3_CUSTOM_DOMAIN",
    ):
        child_environment.pop(name, None)
    child_environment.update(environment)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; "
            "from compose.setup_local_gitlab import "
            "resolve_gitlab_setup_url, resolve_s3_custom_domain; "
            "print(json.dumps([resolve_gitlab_setup_url('localhost:9080'), "
            "resolve_s3_custom_domain('http://rustfs:9000', 'dev-bucket')]))",
        ],
        env=child_environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == expected


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


@pytest.mark.skip_if_lighttest
def test_setup_client_finds_real_group_and_validates_token(
    setup_client: PythonGitLabClient,
) -> None:
    group = setup_client.find_group(settings.GITLAB_GROUP_NAME)
    assert group is not None
    assert str(group["id"]) == str(settings.GITLAB_GROUP_ID)
    assert setup_client.token_can_access_group(
        str(settings.GITLAB_GROUP_ID), settings.GITLAB_TOKEN
    )


@pytest.mark.skip_if_lighttest
def test_setup_client_returns_none_only_for_real_missing_group(
    setup_client: PythonGitLabClient,
) -> None:
    assert setup_client.find_group(f"{settings.GITLAB_GROUP_NAME}/{uuid4()}") is None


@pytest.mark.skip_if_lighttest
def test_setup_client_rejects_invalid_group_credential(
    setup_client: PythonGitLabClient,
) -> None:
    assert not setup_client.token_can_access_group(
        str(settings.GITLAB_GROUP_ID), f"invalid-{uuid4()}"
    )


@pytest.mark.skip_if_lighttest
def test_setup_create_authentication_error_is_not_retried(
    setup_client: PythonGitLabClient,
) -> None:
    invalid_client = PythonGitLabClient(setup_client.base_url, f"invalid-{uuid4()}")
    responses: list[Response] = []

    def observe(response: Response, **kwargs: Any) -> None:
        responses.append(response)

    invalid_client.admin.session.hooks["response"].append(observe)
    try:
        with pytest.raises(gitlab.exceptions.GitlabAuthenticationError) as raised:
            invalid_client.create_group(f"setup-invalid-{uuid4()}")
        assert raised.value.response_code == HTTPStatus.UNAUTHORIZED
        assert len(responses) == 1
        assert raised.value.response_body == responses[0].content
    finally:
        invalid_client.admin.session.close()


def test_private_env_update_preserves_user_values_and_is_idempotent(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Developer overrides\nCUSTOM=value\nMANAGED=old\nMANAGED=duplicate\n",
        encoding="utf-8",
    )
    values: dict[str, str] = {"MANAGED": "new", "AWS_STORAGE_BUCKET_NAME": "dev"}
    assert update_env_file(env_file, values) is True
    assert read_env_file(env_file) == {"CUSTOM": "value", **values}
    assert env_file.read_text(encoding="utf-8").count("MANAGED=") == 1
    assert update_env_file(env_file, values) is False
    assert env_file.stat().st_mode & 0o777 == PRIVATE_ENV_MODE


@pytest.fixture
def bootstrap_groups() -> Generator[tuple[PythonGitLabClient, list[str]]]:
    """Use local bootstrap credentials and delete only this test's groups."""
    client = PythonGitLabClient(
        f"{settings.GITLAB_HTTP_PROTOCOL}://{settings.GITLAB_HOST_URL}",
        os.environ["GITLAB_BOOTSTRAP_TOKEN"],
    )
    names: list[str] = []
    try:
        client.admin.auth()
        assert client.admin.user is not None
        assert client.admin.user.is_admin
        yield client, names
    finally:
        for name in names:
            group = client.find_group(name)
            if group is not None:
                client.admin.groups.delete(group["id"])
        client.admin.session.close()


@LOCAL_GITLAB
@pytest.mark.skip_if_lighttest
def test_real_group_and_token_are_created_then_reused(
    bootstrap_groups: tuple[PythonGitLabClient, list[str]],
) -> None:
    client, names = bootstrap_groups
    group_name: str = f"setup-test-{uuid4()}"
    token_name: str = f"integration-{uuid4()}"
    names.append(group_name)
    assert client.find_group(group_name) is None
    first = provision_gitlab(
        client, group_name=group_name, token_name=token_name, current_token=None
    )
    assert first.group_created
    assert first.token_created
    assert client.token_can_access_group(first.group_id, first.group_token)
    tokens = client.list_group_tokens(first.group_id)
    assert len(tokens) == 1
    repeated = provision_gitlab(
        client,
        group_name=group_name,
        token_name=token_name,
        current_token=first.group_token,
    )
    assert not repeated.group_created
    assert not repeated.token_created
    assert repeated.group_id == first.group_id
    reused_credential: bool = repeated.group_token == first.group_token
    assert reused_credential
    assert [token["id"] for token in client.list_group_tokens(first.group_id)] == [
        tokens[0]["id"]
    ]


@LOCAL_GITLAB
@pytest.mark.skip_if_lighttest
def test_invalid_credential_replaces_only_its_named_group_token(
    bootstrap_groups: tuple[PythonGitLabClient, list[str]],
) -> None:
    client, names = bootstrap_groups
    group_name: str = f"setup-test-{uuid4()}"
    token_name: str = f"integration-{uuid4()}"
    names.append(group_name)
    first = provision_gitlab(
        client, group_name=group_name, token_name=token_name, current_token=None
    )
    original = client.list_group_tokens(first.group_id)[0]
    unrelated = client.create_group_token(first.group_id, "unrelated")
    replacement = provision_gitlab(
        client,
        group_name=group_name,
        token_name=token_name,
        current_token=f"invalid-{uuid4()}",
    )
    assert not replacement.group_created
    assert replacement.token_created
    assert client.token_can_access_group(first.group_id, replacement.group_token)
    assert not client.token_can_access_group(first.group_id, first.group_token)
    active_ids: set[int] = {
        token["id"] for token in client.list_group_tokens(first.group_id)
    }
    assert original["id"] not in active_ids
    assert unrelated["id"] in active_ids


@LOCAL_GITLAB
@pytest.mark.skip_if_lighttest
def test_real_setup_cli_provisions_isolated_dev_and_test_resources(
    bootstrap_groups: tuple[PythonGitLabClient, list[str]], tmp_path: Path
) -> None:
    client, names = bootstrap_groups
    dev_name: str = f"setup-dev-{uuid4()}"
    test_name: str = f"setup-test-{uuid4()}"
    names.extend([dev_name, test_name])
    env_template = tmp_path / ".env.dist"
    test_template = tmp_path / "test.env.dist"
    env_file = tmp_path / ".env"
    test_file = tmp_path / "test.env"
    env_template.write_text("CUSTOM_DEV=preserved\n", encoding="utf-8")
    test_template.write_text("CUSTOM_TEST=preserved\n", encoding="utf-8")
    environment: dict[str, str] = {
        **os.environ,
        "GITLAB_GROUP_NAME": dev_name,
        "GITLAB_TEST_GROUP_NAME": test_name,
        "GITLAB_HOST_URL": settings.GITLAB_HOST_URL,
        "GITLAB_SETUP_URL": client.base_url,
        "GITLAB_GROUP_TOKEN_NAME": "integration-dev",
        "GITLAB_TEST_GROUP_TOKEN_NAME": "integration-test",
        "LOCAL_AWS_STORAGE_BUCKET_NAME": "dev-bucket",
        "LOCAL_AWS_TEST_STORAGE_BUCKET_NAME": "test-bucket",
        "AWS_S3_ENDPOINT_URL": "http://rustfs:9000",
        "AWS_S3_BROWSER_ENDPOINT_URL": "http://localhost:9000",
    }
    environment.pop("AWS_S3_CUSTOM_DOMAIN", None)
    command: list[str] = [
        sys.executable,
        "-m",
        "compose.setup_local_gitlab",
        "--env-file",
        str(env_file),
        "--env-template",
        str(env_template),
        "--test-env-file",
        str(test_file),
        "--test-env-template",
        str(test_template),
    ]
    subprocess.run(  # noqa: S603 - fixed module and test-owned paths
        command,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    development = read_env_file(env_file)
    testing = read_env_file(test_file)
    assert development["CUSTOM_DEV"] == "preserved"
    assert testing["CUSTOM_TEST"] == "preserved"
    assert development["GITLAB_GROUP_NAME"] == dev_name
    assert testing["GITLAB_GROUP_NAME"] == test_name
    assert development["GITLAB_GROUP_ID"] != testing["GITLAB_GROUP_ID"]
    test_group_defaults: dict[str, Any] = client.admin.groups.get(
        testing["GITLAB_GROUP_ID"]
    ).default_branch_protection_defaults
    assert test_group_defaults == {
        "allowed_to_push": [{"access_level": 30}],
        "allowed_to_merge": [{"access_level": 30}],
        "allow_force_push": True,
        "code_owner_approval_required": False,
        "developer_can_initial_push": False,
    }
    separate_credentials: bool = development["GITLAB_TOKEN"] != testing["GITLAB_TOKEN"]
    assert separate_credentials
    for values in (development, testing):
        valid: bool = client.token_can_access_group(
            values["GITLAB_GROUP_ID"], values["GITLAB_TOKEN"]
        )
        assert valid
    assert not client.token_can_access_group(
        testing["GITLAB_GROUP_ID"], development["GITLAB_TOKEN"]
    )
    assert not client.token_can_access_group(
        development["GITLAB_GROUP_ID"], testing["GITLAB_TOKEN"]
    )
    assert development["AWS_STORAGE_BUCKET_NAME"] == "dev-bucket"
    assert testing["AWS_STORAGE_BUCKET_NAME"] == "test-bucket"
    assert development["AWS_S3_CUSTOM_DOMAIN"] == "localhost:9000/dev-bucket"
    assert testing["AWS_S3_CUSTOM_DOMAIN"] == "localhost:9000/test-bucket"
    assert testing["GIT_CONFIG_KEY_0"] == "safe.directory"
    assert env_file.stat().st_mode & 0o777 == PRIVATE_ENV_MODE
    assert test_file.stat().st_mode & 0o777 == PRIVATE_ENV_MODE
    subprocess.run(  # noqa: S603 - fixed module and test-owned paths
        command,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    env_unchanged: bool = read_env_file(env_file) == development
    test_unchanged: bool = read_env_file(test_file) == testing
    assert env_unchanged
    assert test_unchanged
