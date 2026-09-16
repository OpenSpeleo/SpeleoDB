from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING
from typing import cast
from uuid import UUID

import pytest
from django.template.loader import render_to_string
from django.test.html import Element
from django.test.html import Parser
from django.urls import reverse

if TYPE_CHECKING:
    from collections.abc import Iterator


ENTITY_ID: UUID = UUID("00000000-0000-0000-0000-000000000001")
RESPONSIVE_COPIES: int = 2


class StrictTemplateParser(Parser):
    """Reject browser-repaired nesting, including mismatched permission actions."""

    def handle_endtag(self, tag: str) -> None:
        assert self.open_tags, f"Unexpected closing tag: {tag}"
        assert self.open_tags[-1].name == tag, (
            f"Closing {tag} inside {self.open_tags[-1].name} at {self.getpos()}"
        )
        super().handle_endtag(tag)


def descendants(element: Element) -> Iterator[Element]:
    for child in element.children:
        if isinstance(child, Element):
            yield child
            yield from descendants(child)


def with_class(element: Element, class_name: str) -> list[Element]:
    return [
        child
        for child in descendants(element)
        if class_name in (dict(child.attributes).get("class") or "").split()
    ]


def render_page(template: str, **context: object) -> Element:
    user: SimpleNamespace = SimpleNamespace(name="Current user", email="me@example.com")
    defaults: dict[str, object] = {
        "user": user,
        "request": SimpleNamespace(url_name="teams"),
        "project": SimpleNamespace(id=ENTITY_ID, name="Project"),
        "team": SimpleNamespace(id=ENTITY_ID, name="Team"),
        "csrf_token": "test-token",
    }
    defaults.update(context)
    parser: StrictTemplateParser = StrictTemplateParser()
    parser.feed(render_to_string(template, defaults))
    parser.close()
    assert not parser.open_tags
    return cast("Element", parser.root)


@pytest.mark.parametrize(
    ("role", "label", "color"),
    [
        ("MEMBER", "Member", "bg-pastel-purple"),
        ("LEADER", "Leader", "bg-pastel-orange"),
        ("INVALID", "Unknown", "bg-srgb-rose-500-30"),
    ],
)
def test_team_roles_render_complete_badges(role: str, label: str, color: str) -> None:
    team: SimpleNamespace = SimpleNamespace(
        id=ENTITY_ID, name="Survey team", country="US", get_member_count=1
    )
    user: SimpleNamespace = SimpleNamespace(
        name="Current user",
        team_memberships=[SimpleNamespace(team=team, role_label=role)],
    )
    page: Element = render_page("pages/teams.html", user=user)
    badges: list[Element] = with_class(page, color)
    assert len(badges) == RESPONSIVE_COPIES
    assert all("".join(badge.children).strip() == label for badge in badges)


@pytest.mark.parametrize("admin", [True, False])
@pytest.mark.parametrize("self_permission", [True, False])
@pytest.mark.parametrize(
    ("template", "is_admin", "collection", "edit_class", "delete_class"),
    [
        (
            "pages/project/user_permissions.html",
            "is_project_admin",
            "permissions",
            "btn_open_edit_perm",
            "btn_delete_perm",
        ),
        (
            "pages/team/memberships.html",
            "is_team_leader",
            "memberships",
            "btn_open_edit_membership",
            "btn_delete_membership",
        ),
    ],
)
def test_person_actions_preserve_permissions_and_nesting(
    template: str,
    is_admin: str,
    collection: str,
    edit_class: str,
    delete_class: str,
    *,
    admin: bool,
    self_permission: bool,
) -> None:
    user: SimpleNamespace = SimpleNamespace(name="Current user", email="me@example.com")
    target: SimpleNamespace = (
        user
        if self_permission
        else SimpleNamespace(name="Other user", email='other+"quote@example.com')
    )
    permission: SimpleNamespace = SimpleNamespace(
        user=target, level_label="READ_ONLY", role_label="MEMBER", team=None
    )
    page: Element = render_page(
        template, user=user, **{is_admin: admin, collection: [permission]}
    )
    expected_count: int = RESPONSIVE_COPIES if admin and not self_permission else 0
    for class_name in (edit_class, delete_class):
        actions: list[Element] = with_class(page, class_name)
        assert len(actions) == expected_count
        for action in actions:
            assert action.name == "span"
            assert dict(action.attributes)["data-user"] == target.email
            assert action.children[0].name == "svg"


@pytest.mark.parametrize("admin", [True, False])
def test_team_permission_actions_preserve_permissions_and_nesting(
    *, admin: bool
) -> None:
    team: SimpleNamespace = SimpleNamespace(id=ENTITY_ID, name='Team "quoted"')
    permission: SimpleNamespace = SimpleNamespace(target=team, level_label="READ_ONLY")
    page: Element = render_page(
        "pages/project/team_permissions.html",
        is_project_admin=admin,
        permissions=[permission],
        available_teams=[team],
    )
    for class_name in ("btn_open_edit_perm", "btn_delete_perm"):
        actions: list[Element] = with_class(page, class_name)
        assert len(actions) == (RESPONSIVE_COPIES if admin else 0)
        for action in actions:
            assert action.name == "span"
            assert dict(action.attributes)["data-team"] == str(ENTITY_ID)


@dataclass
class TeamAccess:
    has_access: bool
    id: UUID = ENTITY_ID
    name: str = "Inherited team"

    def is_member(self, _user: object) -> bool:
        return self.has_access


@pytest.mark.parametrize("has_team_access", [True, False])
def test_inherited_permission_team_links_are_balanced(*, has_team_access: bool) -> None:
    team: TeamAccess = TeamAccess(has_access=has_team_access)
    permission: SimpleNamespace = SimpleNamespace(
        user=SimpleNamespace(name="Collaborator", email="member@example.com"),
        level_label="READ_ONLY",
        team=team,
    )
    page: Element = render_page(
        "pages/project/user_permissions.html", permissions=[permission]
    )
    assert not with_class(page, "btn_open_edit_perm")
    assert not with_class(page, "btn_delete_perm")
    links: list[Element] = [
        element
        for element in descendants(page)
        if element.name == "a"
        and dict(element.attributes).get("href")
        == reverse("private:team_memberships", kwargs={"team_id": ENTITY_ID})
    ]
    assert len(links) == (RESPONSIVE_COPIES if has_team_access else 0)


@pytest.mark.parametrize(
    "url_name", ["user_dashboard", "projects", "map_viewer", "teams"]
)
def test_private_navigation_has_no_nested_interactive_elements(url_name: str) -> None:
    page: Element = render_page(
        "base_private.html", request=SimpleNamespace(url_name=url_name)
    )
    sidebar: Element = next(
        element
        for element in descendants(page)
        if dict(element.attributes).get("id") == "sidebar"
    )
    active_items: list[Element] = with_class(sidebar, "bg-slate-900")
    assert len(active_items) == 1
    for element in descendants(page):
        if element.name in {"a", "button"}:
            assert not any(
                child.name in {"a", "button", "input", "select", "textarea"}
                for child in descendants(element)
            )
