# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_NODE_MAJOR = "26"


def _find_setup_node_steps(value: object) -> list[dict[str, Any]]:
    setup_steps: list[dict[str, Any]] = []

    if isinstance(value, dict):
        if str(value.get("uses", "")).startswith("actions/setup-node@"):
            setup_steps.append(value)
        for nested_value in value.values():
            setup_steps.extend(_find_setup_node_steps(nested_value))
    elif isinstance(value, list):
        for nested_value in value:
            setup_steps.extend(_find_setup_node_steps(nested_value))

    return setup_steps


def test_node_major_is_consistent_across_package_metadata() -> None:
    node_major = (REPOSITORY_ROOT / ".node-version").read_text(encoding="utf-8").strip()
    package: dict[str, Any] = json.loads(
        (REPOSITORY_ROOT / "package.json").read_text(encoding="utf-8")
    )
    package_lock: dict[str, Any] = json.loads(
        (REPOSITORY_ROOT / "package-lock.json").read_text(encoding="utf-8")
    )

    assert node_major == EXPECTED_NODE_MAJOR
    assert package["engines"]["node"] == f"{node_major}.*"
    assert package_lock["packages"][""]["engines"]["node"] == f"{node_major}.*"


def test_github_actions_read_node_version_file() -> None:
    setup_steps: list[dict[str, Any]] = []
    workflow_paths = sorted((REPOSITORY_ROOT / ".github" / "workflows").glob("*.y*ml"))

    for workflow_path in workflow_paths:
        workflow: dict[str, Any] = yaml.safe_load(
            workflow_path.read_text(encoding="utf-8")
        )
        setup_steps.extend(_find_setup_node_steps(workflow))

    assert setup_steps
    for setup_step in setup_steps:
        inputs: dict[str, Any] = setup_step.get("with", {})
        assert inputs["node-version-file"] == ".node-version"
        assert "node-version" not in inputs


def test_compose_dockerfile_reads_node_version_file() -> None:
    dockerfile = (REPOSITORY_ROOT / "compose" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "COPY .node-version /tmp/.node-version" in dockerfile
    assert "< /tmp/.node-version" in dockerfile
    assert "setup_${NODE_MAJOR}.x" in dockerfile
    assert 'grep -Eq "^v${NODE_MAJOR}\\\\."' in dockerfile
    assert "setup_22.x" not in dockerfile
    assert "setup_26.x" not in dockerfile


def test_railpack_reads_node_version_file_for_node_commands() -> None:
    railpack: dict[str, Any] = json.loads(
        (REPOSITORY_ROOT / "railpack.json").read_text(encoding="utf-8")
    )
    commands: list[str] = [
        command["cmd"] for command in railpack["steps"]["build"]["commands"]
    ]
    expected_prefix = "mise exec -- "
    node_commands = [
        command for command in commands if command.startswith(expected_prefix)
    ]

    assert "node" not in railpack["packages"]
    assert node_commands == [
        f"{expected_prefix}node --version",
        f"{expected_prefix}npm ci",
        f"{expected_prefix}npm run build",
    ]
