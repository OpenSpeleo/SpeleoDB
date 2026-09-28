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


def test_application_services_build_the_development_target() -> None:
    compose_config: dict[str, Any] = yaml.safe_load(
        (REPOSITORY_ROOT / "local.yml").read_text(encoding="utf-8")
    )
    for service_name in (
        "django",
        "django-webserver",
        "celery-worker",
        "celery-beat",
        "setup",
    ):
        build: dict[str, Any] = compose_config["services"][service_name]["build"]
        assert build["dockerfile"] == "./compose/Dockerfile"
        assert build["target"] == "development"


def test_production_ci_builds_the_standalone_image_without_publication() -> None:
    workflow: dict[str, Any] = yaml.safe_load(
        (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
    )
    build_step: dict[str, Any] = next(
        step
        for step in workflow["jobs"]["production-image"]["steps"]
        if str(step.get("uses", "")).startswith("docker/build-push-action@")
    )
    inputs: dict[str, Any] = build_step["with"]
    assert inputs["context"] == "."
    assert inputs["file"] == "compose/Dockerfile"
    assert inputs["target"] == "production"
    assert inputs["platforms"] == "linux/amd64"
    assert inputs["push"] is False


def test_flake_selects_node_major_from_the_shared_version_file() -> None:
    flake: str = (REPOSITORY_ROOT / "flake.nix").read_text(encoding="utf-8")
    assert "builtins.readFile ./.node-version" in flake
    assert 'pkgs."nodejs_${nodeMajor}"' in flake
