"""Country filtering through real querysets and the admin's parameter interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.surveys.admin import ProjectAdmin
from speleodb.surveys.models import Project
from speleodb.utils.admin_filters import ProjectCountryFilter

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from django.http import HttpRequest

pytestmark = pytest.mark.django_db


@pytest.fixture
def projects() -> list[Project]:
    return [ProjectFactory.create(country=country) for country in ("US", "FR", "US")]


def _country_filter(
    selection: str | None = None,
) -> tuple[ProjectCountryFilter, HttpRequest, ProjectAdmin]:
    request = RequestFactory().get("/admin/")
    project_admin = ProjectAdmin(Project, AdminSite())
    params: dict[str, list[str]] = {} if selection is None else {"country": [selection]}
    country_filter = ProjectCountryFilter(
        request=request, params=params, model=Project, model_admin=project_admin
    )
    return country_filter, request, project_admin


def test_lookups_are_distinct_sorted_labels_and_follow_deleted_projects(
    projects: list[Project],
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    country_filter, request, project_admin = _country_filter()
    with django_assert_num_queries(1):
        assert country_filter.lookups(request, project_admin) == [
            ("FR", "France"),
            ("US", "USA"),
        ]
    Project.objects.filter(country="US").delete()
    assert country_filter.lookups(request, project_admin) == [("FR", "France")]


def test_lookups_are_empty_without_projects() -> None:
    country_filter, request, project_admin = _country_filter()
    assert country_filter.lookups(request, project_admin) == []


@pytest.mark.parametrize(
    ("selection", "expected_countries"),
    [
        ("US", ["US", "US"]),
        (None, ["FR", "US", "US"]),
        ("", ["FR", "US", "US"]),
        ("XX", []),
    ],
)
def test_country_filter_applies_request_selection(
    projects: list[Project], selection: str | None, expected_countries: list[str]
) -> None:
    country_filter, request, _ = _country_filter(selection)
    filtered = country_filter.queryset(request, Project.objects.all())
    assert list(filtered.order_by("country").values_list("country", flat=True)) == (
        expected_countries
    )
