from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest
from django.urls import reverse

from frontend_private.tests.test_template_lint_regressions import ENTITY_ID
from frontend_private.tests.test_template_lint_regressions import descendants
from frontend_private.tests.test_template_lint_regressions import render_page
from frontend_private.tests.test_template_lint_regressions import with_class
from speleodb.common.enums import ProjectType
from speleodb.surveys.templatetags.project_types import get_project_type_color


@pytest.mark.parametrize("access", ["owner", "admin", "reader", "unlocked"])
def test_project_names_and_lock_controls_match_in_desktop_and_mobile(
    access: str,
) -> None:
    user = SimpleNamespace(name="Current user", email="me@example.com")
    editor = user if access == "owner" else SimpleNamespace(email="editor@example.com")
    project = SimpleNamespace(
        id=ENTITY_ID,
        name="Survey project",
        type="compass",
        country=SimpleNamespace(code="US"),
        modified_date=dt.datetime(2026, 1, 2, tzinfo=dt.UTC),
    )
    project_data = SimpleNamespace(
        project=project,
        level_label="ADMIN" if access == "admin" else "READ_AND_WRITE",
        active_mutex=None
        if access == "unlocked"
        else SimpleNamespace(user=editor, creation_date=project.modified_date),
    )
    page = render_page(
        "pages/projects.html",
        user=user,
        projects_by_country={"United States": [project_data]},
    )
    target = reverse("private:project_details", kwargs={"project_id": ENTITY_ID})
    assert [
        dict(link.attributes)["href"] for link in with_class(page, "project-name-link")
    ] == [target, target]
    assert [
        dict(link.attributes)["href"]
        for link in with_class(page, "project-open-button")
    ] == [target, target]
    unlocks = with_class(page, "btn-unlock")
    if access in {"reader", "unlocked"}:
        assert not unlocks
    else:
        # Mobile card and desktop lock column; no duplicate in Open's column.
        assert len(unlocks) == 2  # noqa: PLR2004 - both responsive copies
        for button in unlocks:
            attributes = dict(button.attributes)
            assert button.name == "button"
            assert attributes["data-editor-email"] == editor.email
            assert attributes["data-project_id"] == str(ENTITY_ID)
            assert attributes["data-force-unlock"] == str(access == "admin").lower()
            assert str(button.children[0]).strip() == (
                "Force Unlock" if access == "admin" else "Unlock"
            )


def test_dashboard_links_and_software_swatches_reference_canonical_badges() -> None:
    page = render_page("pages/dashboard.html")
    cards = with_class(page, "stat-card")
    assert [dict(card.attributes).get("href") for card in cards] == [
        reverse("private:projects"),
        reverse("private:teams"),
        None,
    ]
    swatches = {
        attributes["data-project-type"]: attributes["class"]
        for element in descendants(page)
        if "data-project-type" in (attributes := dict(element.attributes))
    }
    assert swatches == {
        project_type.value: get_project_type_color(project_type)
        for project_type in ProjectType
    }


def test_unknown_software_uses_canonical_other_badge() -> None:
    assert get_project_type_color("unknown") == get_project_type_color(
        ProjectType.OTHER
    )
