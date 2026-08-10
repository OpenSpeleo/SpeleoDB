# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import pwd
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from compose.setup_local_gitlab import read_env_file

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ROOT_MAPBOX_INTERPOLATION = "${MAPBOX_API_TOKEN:-}"
NODE_MODULES_VOLUME = "speleodb_local_web_node_modules"
PREPARE_NODE_MODULES = REPOSITORY_ROOT / "compose" / "prepare_node_modules"


def test_root_dotenv_is_authoritative_for_local_mapbox_token() -> None:
    compose_config: dict[str, Any] = yaml.safe_load(
        (REPOSITORY_ROOT / "local.yml").read_text(encoding="utf-8")
    )

    services: dict[str, Any] = compose_config["services"]
    assert (
        services["django"]["environment"]["MAPBOX_API_TOKEN"]
        == ROOT_MAPBOX_INTERPOLATION
    )
    assert (
        services["django-webserver"]["environment"]["MAPBOX_API_TOKEN"]
        == ROOT_MAPBOX_INTERPOLATION
    )

    django_environment = read_env_file(REPOSITORY_ROOT / ".envs" / ".django")
    assert "MAPBOX_API_TOKEN" not in django_environment


def test_local_application_services_share_dev_user_node_modules() -> None:
    compose_config: dict[str, Any] = yaml.safe_load(
        (REPOSITORY_ROOT / "local.yml").read_text(encoding="utf-8")
    )

    services: dict[str, Any] = compose_config["services"]
    for service_name in ("django", "django-webserver"):
        service: dict[str, Any] = services[service_name]
        assert service["user"] == "dev-user"
        _assert_node_modules_volume(service)

    setup_service: dict[str, Any] = services["setup"]
    assert setup_service["user"] == "root"
    _assert_node_modules_volume(setup_service)

    dockerignore_entries = {
        line.strip()
        for line in (REPOSITORY_ROOT / ".dockerignore")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "node_modules" in dockerignore_entries

    devcontainer_config = (
        REPOSITORY_ROOT / ".devcontainer" / "devcontainer.json"
    ).read_text(encoding="utf-8")
    assert '"updateRemoteUserUID": false' in devcontainer_config


def _assert_node_modules_volume(service: dict[str, Any]) -> None:
    volume = next(
        mount
        for mount in service["volumes"]
        if isinstance(mount, dict) and mount.get("target") == "/app/node_modules"
    )
    assert volume["type"] == "volume"
    assert volume["source"] == NODE_MODULES_VOLUME
    assert volume["volume"]["nocopy"] is True


def _run_ownership_preparation(
    node_modules_dir: Path,
    *,
    owner: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "SPELEODB_NODE_MODULES_DIR": str(node_modules_dir),
            "SPELEODB_NODE_MODULES_USER": owner,
            "SPELEODB_NODE_MODULES_GROUP": owner,
        }
    )
    return subprocess.run(  # noqa: S603
        ["/bin/bash", str(PREPARE_NODE_MODULES)],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )


def test_node_modules_preparation_is_idempotent_for_current_owner(
    tmp_path: Path,
) -> None:
    node_modules_dir = tmp_path / "node_modules"
    node_modules_dir.mkdir()
    sentinel = node_modules_dir / "installed-package"
    sentinel.write_text("preserved", encoding="utf-8")
    current_owner = pwd.getpwuid(os.geteuid()).pw_name

    first_result = _run_ownership_preparation(
        node_modules_dir,
        owner=current_owner,
    )
    second_result = _run_ownership_preparation(
        node_modules_dir,
        owner=current_owner,
    )

    assert "already current" in first_result.stdout
    assert "already current" in second_result.stdout
    assert sentinel.read_text(encoding="utf-8") == "preserved"


@pytest.mark.skipif(os.geteuid() != 0, reason="Ownership migration requires root")
def test_node_modules_preparation_migrates_legacy_root_volume(
    tmp_path: Path,
) -> None:
    node_modules_dir = tmp_path / "node_modules"
    vite_temp_dir = node_modules_dir / ".vite-temp"
    vite_temp_dir.mkdir(parents=True)
    config_file = vite_temp_dir / "vite.config.mjs"
    config_file.write_text("export default {};", encoding="utf-8")
    dev_user = pwd.getpwnam("dev-user")

    result = _run_ownership_preparation(node_modules_dir, owner=dev_user.pw_name)

    assert "Migrating Node dependency volume ownership" in result.stdout
    for path in (node_modules_dir, vite_temp_dir, config_file):
        path_stat = path.stat()
        assert path_stat.st_uid == dev_user.pw_uid
        assert path_stat.st_gid == dev_user.pw_gid
