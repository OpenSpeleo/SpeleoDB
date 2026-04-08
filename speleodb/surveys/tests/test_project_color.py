# -*- coding: utf-8 -*-

from __future__ import annotations

import pytest
from django.template.loader import render_to_string
from rest_framework.exceptions import ValidationError

from speleodb.api.v1.serializers.gps_track import GPSTrackSerializer
from speleodb.api.v1.serializers.project import ProjectSerializer
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.common.enums import ColorPalette
from speleodb.surveys.templatetags.project_colors import country_flag
from speleodb.surveys.templatetags.project_colors import get_project_color_palette

# ── ColorPalette enum ───────────────────────────────────────────────


def test_random_color_always_from_palette() -> None:
    for _ in range(50):
        assert ColorPalette.random_color() in ColorPalette.COLORS


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("#e41a1c", True),
        ("#ABCDEF", True),
        ("#000000", True),
        ("red", False),
        ("#xyz123", False),
        ("123456", False),
        ("#12345", False),
        ("#1234567", False),
        ("", False),
        ("#", False),
    ],
)
def test_is_valid_hex(value: str, expected: bool) -> None:
    assert ColorPalette.is_valid_hex(value) is expected


# ── Model defaults ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_project_default_color_in_palette() -> None:
    project = ProjectFactory.create()
    assert project.color in ColorPalette.COLORS


@pytest.mark.django_db
def test_project_accepts_custom_hex() -> None:
    project = ProjectFactory.create(color="#abcdef")
    assert project.color == "#abcdef"


# ── Serializer validate_color (shared logic) ────────────────────────


@pytest.mark.parametrize(
    "color",
    ["#e41a1c", "#ABCDEF", "#000000", "#ffffff", "#123456"],
)
def test_project_validate_color_accepts_valid_hex(color: str) -> None:
    serializer = ProjectSerializer()
    assert serializer.validate_color(color) == color.lower()


@pytest.mark.parametrize(
    "color",
    ["red", "#xyz123", "123456", "#12345", "#1234567", "", "#"],
)
def test_project_validate_color_rejects_invalid(color: str) -> None:
    serializer = ProjectSerializer()
    with pytest.raises(ValidationError):
        serializer.validate_color(color)


@pytest.mark.parametrize(
    "color",
    ["#e41a1c", "#ABCDEF", "#000000"],
)
def test_gps_track_validate_color_accepts_valid_hex(color: str) -> None:
    serializer = GPSTrackSerializer()
    assert serializer.validate_color(color) == color.lower()


@pytest.mark.parametrize(
    "color",
    ["red", "#xyz123", "123456"],
)
def test_gps_track_validate_color_rejects_invalid(color: str) -> None:
    serializer = GPSTrackSerializer()
    with pytest.raises(ValidationError):
        serializer.validate_color(color)


# ── Template tags ───────────────────────────────────────────────────


def test_get_project_color_palette_returns_palette() -> None:
    assert get_project_color_palette() == ColorPalette.COLORS


def test_country_flag_converts_fr() -> None:
    assert country_flag("FR") == "\U0001f1eb\U0001f1f7"


@pytest.mark.parametrize(
    "code",
    ["", "X", "ABC", None],
)
def test_country_flag_returns_empty_for_invalid(code: str | None) -> None:
    assert country_flag(code) == ""


# ── Disabled state rendering ────────────────────────────────────────


@pytest.mark.django_db
def test_details_template_hides_color_presets_when_readonly() -> None:
    """When has_write_access is False, color presets and picker button are hidden."""

    project = ProjectFactory.create(color="#e41a1c")
    html = render_to_string(
        "pages/project/details.html",
        {
            "project": project,
            "has_write_access": False,
            "is_project_admin": False,
            "request": type("R", (), {"url_name": "project_details"})(),
        },
    )
    assert 'class="color-picker-group color-picker-disabled"' in html
    assert 'class="color-preset' not in html
    assert 'id="color-picker-btn"' not in html
    assert "cursor-not-allowed" in html


@pytest.mark.django_db
def test_details_template_shows_color_presets_when_writable() -> None:
    """When has_write_access is True, color presets and picker button are shown."""

    project = ProjectFactory.create(color="#377eb8")
    html = render_to_string(
        "pages/project/details.html",
        {
            "project": project,
            "has_write_access": True,
            "is_project_admin": False,
            "request": type("R", (), {"url_name": "project_details"})(),
        },
    )
    assert 'class="color-picker-group"' in html
    assert "data-color=" in html
    assert 'id="color-picker-btn"' in html
    assert "bg-indigo-500" in html
    assert "cursor-not-allowed" not in html
