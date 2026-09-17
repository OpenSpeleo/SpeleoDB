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
    ("url_name", "active_route"),
    [
        ("user_dashboard", "user_dashboard"),
        ("projects", "projects"),
        ("map_viewer", "map_viewer"),
        ("teams", "teams"),
        ("gis_geometries", "gis_geometries"),
        ("gis_geometry_details", "gis_geometries"),
        ("gis_geometry_user_permissions", "gis_geometries"),
        ("gis_geometry_danger_zone", "gis_geometries"),
        ("gis_layers", "gis_layers"),
        ("gis_layer_details", "gis_layers"),
        ("gis_layer_user_permissions", "gis_layers"),
        ("gis_layer_danger_zone", "gis_layers"),
        *[
            (route, "cylinder_fleets")
            for route in (
                "cylinder_fleets",
                "cylinder_fleet_new",
                "cylinder_fleet_details",
                "cylinder_fleet_danger_zone",
                "cylinder_fleet_user_permissions",
                "cylinder_fleet_history",
                "cylinder_fleet_watchlist",
                "cylinder_fleet_needs_hydro",
                "cylinder_fleet_needs_visual",
            )
        ],
        *[
            (route, "experiments")
            for route in (
                "experiments",
                "experiment_new",
                "experiment_details",
                "experiment_danger_zone",
                "experiment_gis_integration",
                "experiment_user_permissions",
                "experiment_data_viewer",
            )
        ],
        *[
            (route, "landmark_collections")
            for route in (
                "landmark_collections",
                "landmark_collection_new",
                "landmark_collection_details",
                "landmark_collection_user_permissions",
                "landmark_collection_gis_integration",
                "landmark_collection_danger_zone",
            )
        ],
        *[
            (route, "sensor_fleets")
            for route in (
                "sensor_fleets",
                "sensor_fleet_new",
                "sensor_fleet_details",
                "sensor_fleet_danger_zone",
                "sensor_fleet_user_permissions",
                "sensor_fleet_history",
                "sensor_fleet_watchlist",
            )
        ],
        ("station_tags", "station_tags"),
        *[
            (route, "surface_networks")
            for route in (
                "surface_networks",
                "surface_network_new",
                "surface_network_details",
                "surface_network_user_permissions",
                "surface_network_gis_integration",
                "surface_network_danger_zone",
            )
        ],
        *[
            (route, "gis_views")
            for route in (
                "gis_views",
                "gis_view_new",
                "gis_view_details",
                "gis_view_gis_integration",
                "gis_view_danger_zone",
            )
        ],
    ],
)
def test_private_navigation_has_no_nested_interactive_elements(
    url_name: str, active_route: str
) -> None:
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
    active_link: Element = next(
        element for element in descendants(active_items[0]) if element.name == "a"
    )
    assert dict(active_link.attributes)["href"] == reverse(f"private:{active_route}")
    navigation: Element = next(
        element for element in descendants(sidebar) if element.name == "ul"
    )
    sections: list[list[Element]] = [[]]
    for child in navigation.children:
        if not isinstance(child, Element):
            continue
        if child.name == "hr":
            sections.append([])
        elif child.name == "li":
            sections[-1].append(child)
    gis_links: list[Element] = [
        element
        for item in sections[1]
        for element in descendants(item)
        if element.name == "a"
    ]
    gis_labels: list[str] = [
        "".join(element.children).strip()
        for link in gis_links
        for element in descendants(link)
        if element.name == "span"
    ]
    assert gis_labels == sorted(gis_labels)
    group: Element = next(
        element
        for element in descendants(sidebar)
        if dict(element.attributes).get("id") == "gis-tooling"
    )
    assert group.name == "details"
    assert "open" not in dict(group.attributes)
    summary: Element = next(
        element for element in descendants(group) if element.name == "summary"
    )
    assert "GIS Tooling" in str(summary)
    current_links: list[Element] = [
        link
        for link in gis_links
        if dict(link.attributes).get("aria-current") == "page"
    ]
    assert current_links == ([active_link] if active_link in gis_links else [])
    first_section_links: list[Element] = [
        element
        for item in sections[0]
        for element in descendants(item)
        if element.name == "a"
    ]
    first_section_urls: list[str | None] = [
        dict(link.attributes).get("href") for link in first_section_links
    ]
    tools_index: int = first_section_urls.index(reverse("private:tool-xls2dmp"))
    assert first_section_urls[tools_index + 1] == reverse("private:map_viewer")
    assert all(
        dict(link.attributes).get("href") != reverse("private:map_viewer")
        for link in gis_links
    )
    for route, label in (
        ("gis_geometries", "GIS Geometries"),
        ("gis_layers", "GIS Layers"),
    ):
        matching_links: list[Element] = [
            link
            for link in descendants(sidebar)
            if link.name == "a"
            and dict(link.attributes).get("href") == reverse(f"private:{route}")
        ]
        assert len(matching_links) == 1
        assert matching_links[0] in gis_links
        assert gis_labels[gis_links.index(matching_links[0])] == label
    # One shared sidebar serves both the mobile drawer and desktop layout.
    assert "lg:static" in (dict(sidebar.attributes).get("class") or "").split()
    for item in sections[1]:
        for element in [item, *descendants(item)]:
            classes: list[str] = (dict(element.attributes).get("class") or "").split()
            assert not {"hidden", "lg:hidden"}.intersection(classes)
    for element in descendants(page):
        if element.name in {"a", "button"}:
            assert not any(
                child.name in {"a", "button", "input", "select", "textarea"}
                for child in descendants(element)
            )
