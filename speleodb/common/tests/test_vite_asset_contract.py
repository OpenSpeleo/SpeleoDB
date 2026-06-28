from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from django.conf import settings

REPOSITORY_ROOT = Path(settings.BASE_DIR)
TEMPLATE_ROOTS = (
    REPOSITORY_ROOT / "frontend_public" / "templates",
    REPOSITORY_ROOT / "frontend_private" / "templates",
    REPOSITORY_ROOT / "frontend_errors" / "templates",
    REPOSITORY_ROOT / "speleodb" / "templates",
)


def template_files() -> list[Path]:
    return sorted(path for root in TEMPLATE_ROOTS for path in root.rglob("*.html"))


def registry() -> dict[str, dict[str, str]]:
    value: Any = json.loads(
        (REPOSITORY_ROOT / "frontend_common" / "entries.json").read_text()
    )
    assert isinstance(value, dict)
    return value


def test_templates_only_execute_the_vite_bootstrap() -> None:
    inline_script = re.compile(
        r"<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script>", re.S
    )
    event_handler = re.compile(
        r"\son(?:click|change|submit|input|load|focus|blur)=", re.I
    )

    for path in template_files():
        source = path.read_text()
        assert event_handler.search(source) is None, path
        for match in inline_script.finditer(source):
            attrs = match.group("attrs")
            if re.search(r"\bsrc\s*=", attrs):
                continue
            assert 'type="application/json"' in attrs, path


def test_templates_have_no_direct_first_party_css_or_javascript() -> None:
    authored_static = re.compile(
        r"\{%\s*static\s+['\"](?P<path>[^'\"]+\.(?:css|js|ts))['\"]\s*%\}"
    )
    for path in template_files():
        for match in authored_static.finditer(path.read_text()):
            assert "/vendors/" in f"/{match.group('path')}", path


def test_every_controller_and_extracted_style_is_registered() -> None:
    entries = registry()
    registered_controllers = {
        name.removeprefix("controller-")
        for name in entries["scripts"]
        if name.startswith("controller-")
    }
    referenced_controllers: set[str] = set()
    referenced_styles: set[str] = set()

    for path in template_files():
        source = path.read_text()
        referenced_controllers.update(
            re.findall(r'data-speleodb-controller="([a-z0-9-]+)"', source)
        )
        referenced_styles.update(
            name
            for invocation in re.findall(r"\{%\s*vite_styles\s+([^%]+)%\}", source)
            for name in re.findall(r"['\"]([^'\"]+)['\"]", invocation)
        )

    assert referenced_controllers <= registered_controllers
    assert referenced_styles <= set(entries["styles"])
    assert registered_controllers <= referenced_controllers

    for section in ("styles", "scripts"):
        for logical_name, relative_path in entries[section].items():
            assert (REPOSITORY_ROOT / relative_path).is_file(), logical_name


def test_root_commands_define_one_vite_pipeline() -> None:
    package: Any = json.loads((REPOSITORY_ROOT / "package.json").read_text())
    scripts: dict[str, str] = package["scripts"]
    assert scripts["build:assets"] == "vite build --mode production"
    assert scripts["dev"] == "vite build --watch --mode development"
    assert scripts["start"] == "npm run dev"
    assert not any("tailwind" in name or "esbuild" in name for name in scripts)
    templates = "\n".join(path.read_text() for path in template_files())
    assert "@vite/client" not in templates
