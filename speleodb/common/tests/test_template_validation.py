from __future__ import annotations

from copy import deepcopy
from io import StringIO
from typing import TYPE_CHECKING

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import Settings


@pytest.fixture
def template_directory(tmp_path: Path, settings: Settings) -> Path:
    templates = deepcopy(settings.TEMPLATES)
    templates[0]["DIRS"] = [str(tmp_path)]
    templates[0]["APP_DIRS"] = False
    settings.TEMPLATES = templates
    return tmp_path


def test_template_validation_accepts_colocated_images(template_directory: Path) -> None:
    (template_directory / "email.html").write_text("Hello {{ name }}")
    (template_directory / "email.txt").write_text("Hello {{ name }}")
    assets = template_directory / "assets"
    assets.mkdir()
    with Image.new("RGB", (1, 1)) as image:
        for suffix in ("jpg", "jpeg", "png"):
            image.save(assets / f"campaign.{suffix}")

    output = StringIO()
    call_command("validate_templates", no_apps=True, stdout=output)

    assert "0 errors found" in output.getvalue()


@pytest.mark.parametrize("suffix", ["html", "txt"])
def test_template_validation_rejects_invalid_source(
    template_directory: Path, suffix: str
) -> None:
    template = template_directory / f"email.{suffix}"
    template.write_text("{% if name %}")
    output = StringIO()

    with pytest.raises(CommandError, match="1 errors found"):
        call_command("validate_templates", no_apps=True, stdout=output)

    assert str(template) in output.getvalue()
    assert "TemplateSyntaxError" in output.getvalue()
