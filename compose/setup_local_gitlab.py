#!/usr/bin/env python

from __future__ import annotations

import argparse
import logging
import os
import shutil
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol

import gitlab
import gitlab.exceptions
from gitlab.const import AccessLevel

if TYPE_CHECKING:
    from gitlab.v4.objects.groups import Group

HTTP_TIMEOUT_SECONDS = 15
GROUP_TOKEN_SCOPES = ["api", "read_repository", "write_repository"]
logger = logging.getLogger(__name__)


class GitLabSetupError(RuntimeError):
    """Raised when the local GitLab instance cannot be provisioned safely."""


class GitLabClient(Protocol):
    def find_group(self, group_name: str) -> dict[str, Any] | None: ...

    def create_group(self, group_name: str) -> dict[str, Any]: ...

    def token_can_access_group(self, group_id: str, token: str) -> bool: ...

    def list_group_tokens(self, group_id: str) -> list[dict[str, Any]]: ...

    def revoke_group_token(self, group_id: str, token_id: str) -> None: ...

    def create_group_token(self, group_id: str, token_name: str) -> dict[str, Any]: ...


class PythonGitLabClient:
    def __init__(self, base_url: str, bootstrap_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.admin = self._connect(bootstrap_token)

    def _connect(self, token: str) -> gitlab.Gitlab:
        return gitlab.Gitlab(
            self.base_url,
            private_token=token,
            timeout=HTTP_TIMEOUT_SECONDS,
            retry_transient_errors=True,
            keep_base_url=self.base_url.startswith("http://"),
        )

    def _group(self, group_id: str) -> Group:
        return self.admin.groups.get(group_id, lazy=True)

    def find_group(self, group_name: str) -> dict[str, Any] | None:
        try:
            group = self.admin.groups.get(group_name)
        except gitlab.exceptions.GitlabGetError as error:
            if error.response_code == HTTPStatus.NOT_FOUND:
                return None
            raise GitLabSetupError(
                f"Unable to retrieve local GitLab group {group_name!r}."
            ) from error
        return {"id": group.id, "name": group.name}

    def create_group(self, group_name: str) -> dict[str, Any]:
        group = self.admin.groups.create({"name": group_name, "path": group_name})
        return {"id": group.id, "name": group.name}

    def token_can_access_group(self, group_id: str, token: str) -> bool:
        try:
            self._connect(token).groups.get(group_id)
        except gitlab.exceptions.GitlabError as error:
            if error.response_code in {
                HTTPStatus.UNAUTHORIZED,
                HTTPStatus.FORBIDDEN,
                HTTPStatus.NOT_FOUND,
            }:
                return False
            raise GitLabSetupError(
                f"Unable to validate the local GitLab group token for {group_id}."
            ) from error
        return True

    def list_group_tokens(self, group_id: str) -> list[dict[str, Any]]:
        tokens = self._group(group_id).access_tokens.list(
            iterator=True,
            state="active",
        )
        return [
            {
                "id": token.id,
                "name": token.name,
                "active": True,
                "expires_at": getattr(token, "expires_at", None),
            }
            for token in tokens
        ]

    def revoke_group_token(self, group_id: str, token_id: str) -> None:
        self._group(group_id).access_tokens.delete(token_id)

    def create_group_token(self, group_id: str, token_name: str) -> dict[str, Any]:
        token = self._group(group_id).access_tokens.create(
            {
                "name": token_name,
                "scopes": GROUP_TOKEN_SCOPES,
                "access_level": AccessLevel.OWNER,
                "expires_at": None,
            },
        )
        return {"id": token.id, "token": token.token}


@dataclass(frozen=True)
class GitLabProvisioningResult:
    group_id: str
    group_token: str
    group_created: bool
    token_created: bool


def provision_gitlab(
    client: GitLabClient,
    *,
    group_name: str,
    token_name: str,
    current_token: str | None,
) -> GitLabProvisioningResult:
    group = client.find_group(group_name)
    group_created = group is None
    if group is None:
        group = client.create_group(group_name)

    group_id = str(group["id"])
    named_tokens = [
        token
        for token in client.list_group_tokens(group_id)
        if token.get("name") == token_name and token.get("active", True)
    ]
    if (
        current_token
        and len(named_tokens) == 1
        and named_tokens[0].get("expires_at") is None
        and client.token_can_access_group(group_id, current_token)
    ):
        return GitLabProvisioningResult(
            group_id=group_id,
            group_token=current_token,
            group_created=group_created,
            token_created=False,
        )

    for token in named_tokens:
        client.revoke_group_token(group_id, str(token["id"]))

    created_token = client.create_group_token(group_id, token_name)
    return GitLabProvisioningResult(
        group_id=group_id,
        group_token=str(created_token["token"]),
        group_created=group_created,
        token_created=True,
    )


def read_env_file(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        return {}

    values: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", maxsplit=1)
        values[key] = value.strip().strip('"').strip("'")
    return values


def initialize_env_file(env_file: Path, env_template: Path) -> bool:
    if env_file.exists():
        env_file.chmod(0o600)
        return False
    if not env_template.is_file():
        raise GitLabSetupError(f"Private env template does not exist: {env_template}")

    env_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = env_file.with_name(f".{env_file.name}.tmp")
    shutil.copyfile(env_template, temporary_file)
    temporary_file.chmod(0o600)
    temporary_file.replace(env_file)
    return True


def update_env_file(env_file: Path, values: dict[str, str]) -> bool:
    for key, value in values.items():
        if "\n" in key or "=" in key or "\n" in value:
            raise ValueError("Environment keys and values must be single-line values.")

    existing_text = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    lines = existing_text.splitlines()
    remaining = values.copy()
    managed_keys = set(values)
    updated_keys: set[str] = set()
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", maxsplit=1)[0]
            if key in managed_keys:
                if key in updated_keys:
                    continue
                output.append(f"{key}={remaining.pop(key)}")
                updated_keys.add(key)
                continue
        output.append(line)

    if remaining:
        if output and output[-1] != "":
            output.append("")
        output.append("# Generated by the local Compose setup service.")
        output.extend(f"{key}={value}" for key, value in remaining.items())

    updated_text = "\n".join(output).rstrip("\n") + "\n"
    if updated_text == existing_text:
        env_file.chmod(0o600)
        return False

    env_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = env_file.with_name(f".{env_file.name}.tmp")
    temporary_file.write_text(updated_text, encoding="utf-8")
    temporary_file.chmod(0o600)
    temporary_file.replace(env_file)
    return True


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise GitLabSetupError(f"{name} must be configured for local setup.")
    return value


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(
        description="Provision local GitLab resources and Django's private env file."
    )
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--env-template", required=True, type=Path)
    arguments = parser.parse_args()

    group_name = _required_environment("GITLAB_GROUP_NAME")
    gitlab_host = _required_environment("GITLAB_HOST_URL")
    bootstrap_token = _required_environment("GITLAB_BOOTSTRAP_TOKEN")
    token_name = _required_environment("GITLAB_GROUP_TOKEN_NAME")
    bucket_name = _required_environment("LOCAL_AWS_STORAGE_BUCKET_NAME")
    s3_endpoint = _required_environment("AWS_S3_ENDPOINT_URL")
    base_url = gitlab_host if "://" in gitlab_host else f"http://{gitlab_host}"
    s3_custom_domain = (
        s3_endpoint.removeprefix("http://").removeprefix("https://").rstrip("/")
        + f"/{bucket_name}"
    )

    env_created = initialize_env_file(arguments.env_file, arguments.env_template)
    current_env = read_env_file(arguments.env_file)
    result = provision_gitlab(
        PythonGitLabClient(base_url, bootstrap_token),
        group_name=group_name,
        token_name=token_name,
        current_token=current_env.get("GITLAB_TOKEN"),
    )
    env_changed = update_env_file(
        arguments.env_file,
        {
            "GITLAB_GROUP_ID": result.group_id,
            "GITLAB_GROUP_NAME": group_name,
            "GITLAB_HOST_URL": gitlab_host,
            "GITLAB_TOKEN": result.group_token,
            "AWS_STORAGE_BUCKET_NAME": bucket_name,
            "AWS_S3_CUSTOM_DOMAIN": s3_custom_domain,
        },
    )

    group_action = "created" if result.group_created else "already exists"
    token_action = "created" if result.token_created else "already valid"
    template_action = "created from template" if env_created else "already exists"
    env_action = "updated" if env_changed else "already current"
    logger.info("GitLab group %s (ID %s).", group_action, result.group_id)
    logger.info("GitLab group token %s.", token_action)
    logger.info("Private Django env file %s.", template_action)
    logger.info("Private Django env file %s.", env_action)


if __name__ == "__main__":
    main()
