# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from compose.setup_local_gitlab import read_env_file

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ROOT_MAPBOX_INTERPOLATION = "${MAPBOX_API_TOKEN:-}"


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
