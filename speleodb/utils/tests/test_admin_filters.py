"""Tests for Django admin functionality."""

from __future__ import annotations

import random
from itertools import cycle
from typing import TYPE_CHECKING

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django_countries import countries

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.surveys.admin import ProjectAdmin
from speleodb.surveys.models import Project
from speleodb.users.tests.factories import UserFactory
from speleodb.utils.admin_filters import ProjectCountryFilter

if TYPE_CHECKING:
    from django_countries.fields import Country

    from speleodb.users.models import User


@pytest.mark.django_db
class TestProjectCountryFilter:
    """Test cases for the ProjectCountryFilter admin filter."""

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return UserFactory.create()

    @pytest.fixture
    def request_factory(self) -> RequestFactory:
        """Create a request factory for testing."""
        return RequestFactory()

    @pytest.fixture
    def admin_site(self) -> AdminSite:
        """Create an admin site for testing."""
        return AdminSite()

    @pytest.fixture
    def project_admin(self, admin_site: AdminSite) -> ProjectAdmin:
        """Create a ProjectAdmin instance for testing."""
        return ProjectAdmin(Project, admin_site)

    @pytest.fixture
    def country_filter(
        self, request_factory: RequestFactory, project_admin: ProjectAdmin
    ) -> ProjectCountryFilter:
        """Create a ProjectCountryFilter instance for testing."""
        request = request_factory.get("/admin/")
        return ProjectCountryFilter(
            request=request,
            params={},
            model=Project,
            model_admin=project_admin,
        )

    @pytest.fixture
    def projects_with_different_countries(self, user: User) -> list[Project]:
        """Create projects with different countries for testing."""
        # Create projects with different countries
        projects = []

        random_countries = random.sample(list(countries), 5)

        for country in random_countries:
            project = ProjectFactory.create(
                country=country.code,
                created_by=user.email,
            )
            projects.append(project)

        return projects

    def test_country_filter_initialization(
        self, country_filter: ProjectCountryFilter
    ) -> None:
        """Test that ProjectCountryFilter initializes correctly."""
        assert country_filter.title == "Country"
        assert country_filter.parameter_name == "country"

    def test_lookups_with_no_projects(
        self,
        country_filter: ProjectCountryFilter,
        request_factory: RequestFactory,
        project_admin: ProjectAdmin,
    ) -> None:
        """Test lookups when no projects exist."""
        request = request_factory.get("/admin/")
        lookups = country_filter.lookups(request, project_admin)

        assert lookups == []

    def test_lookups_with_projects(
        self,
        country_filter: ProjectCountryFilter,
        request_factory: RequestFactory,
        project_admin: ProjectAdmin,
        projects_with_different_countries: list[Project],
    ) -> None:
        """Test lookups with existing projects."""
        request = request_factory.get("/admin/")
        lookups = country_filter.lookups(request, project_admin)

        # Should return countries in alphabetical order
        expected_countries: list[Country] = [
            p.country for p in projects_with_different_countries
        ]
        assert len(lookups) == len(expected_countries)

        # Check that all returned countries are in alphabetical order
        returned_codes = [code for code, _ in lookups]
        assert returned_codes == sorted(
            [c.code for c in expected_countries if c.code is not None]
        )

        # Check that country names are correct
        for code, name in lookups:
            assert dict(countries)[code] == name

    def test_lookups_returns_distinct_countries_only(
        self,
        country_filter: ProjectCountryFilter,
        request_factory: RequestFactory,
        project_admin: ProjectAdmin,
        user: User,
    ) -> None:
        """Test that lookups only returns distinct countries."""
        # Create multiple projects with the same country
        country_A, country_B = random.sample(list(countries), 2)  # noqa: N806
        for _ in range(5):
            _ = ProjectFactory.create(
                country=country_A.code,  # Same country for all
                created_by=user.email,
            )

        # Create one project with a different country
        _ = ProjectFactory.create(
            country=country_B.code,
            created_by=user.email,
        )

        request = request_factory.get("/admin/")
        lookups = country_filter.lookups(request, project_admin)

        # Should only return 2 countries (FR, US) in alphabetical order
        assert len(lookups) == 2  # noqa: PLR2004
        assert sorted([code for code, _ in lookups]) == sorted(
            [country_A.code, country_B.code]
        )

    def test_queryset_filtering_with_valid_country(
        self,
        country_filter: ProjectCountryFilter,
        request_factory: RequestFactory,
        projects_with_different_countries: list[Project],
    ) -> None:
        """Test queryset filtering with a valid country selection."""

        countries: list[str] = [p.country for p in projects_with_different_countries]

        # Set the filter value to first country
        country_filter.value = lambda: countries[0]

        queryset = Project.objects.all()
        request = request_factory.get("/admin/")
        filtered_queryset = country_filter.queryset(request, queryset)

        # Should only return projects with country index 0
        assert filtered_queryset.count() == 1
        first_project = filtered_queryset.first()
        assert first_project is not None
        assert first_project.country == countries[0]

    def test_queryset_filtering_with_no_selection(
        self,
        country_filter: ProjectCountryFilter,
        request_factory: RequestFactory,
        projects_with_different_countries: list[Project],
    ) -> None:
        """Test queryset filtering when no country is selected."""
        # Set the filter value to None (no selection)
        country_filter.value = lambda: None

        queryset = Project.objects.all()
        request = request_factory.get("/admin/")
        filtered_queryset = country_filter.queryset(request, queryset)

        # Should return all projects (no filtering)
        assert filtered_queryset.count() == len(projects_with_different_countries)

    def test_queryset_filtering_with_empty_selection(
        self,
        country_filter: ProjectCountryFilter,
        request_factory: RequestFactory,
        projects_with_different_countries: list[Project],
    ) -> None:
        """Test queryset filtering with empty string selection."""
        # Set the filter value to empty string
        country_filter.value = lambda: ""

        queryset = Project.objects.all()
        request = request_factory.get("/admin/")
        filtered_queryset = country_filter.queryset(request, queryset)

        # Should return all projects (no filtering)
        assert filtered_queryset.count() == len(projects_with_different_countries)

    def test_queryset_filtering_with_nonexistent_country(
        self,
        country_filter: ProjectCountryFilter,
        request_factory: RequestFactory,
        projects_with_different_countries: list[Project],
    ) -> None:
        """Test queryset filtering with a country that doesn't exist in projects."""
        # Set the filter value to a country that doesn't exist in our test data
        country_filter.value = lambda: "XX"

        queryset = Project.objects.all()
        request = request_factory.get("/admin/")
        filtered_queryset = country_filter.queryset(request, queryset)

        # Should return no projects
        assert filtered_queryset.count() == 0

    def test_lookups_ordering_alphabetical(
        self,
        country_filter: ProjectCountryFilter,
        request_factory: RequestFactory,
        project_admin: ProjectAdmin,
        user: User,
    ) -> None:
        """Test that lookups returns countries in alphabetical order."""
        # Create projects with countries in random order (using valid country codes)
        countries_random = random.sample(list(countries), 5)

        for country in countries_random:
            _ = ProjectFactory.create(
                country=country.code,
                created_by=user.email,
            )

        request = request_factory.get("/admin/")
        lookups = country_filter.lookups(request, project_admin)

        # Should return countries in alphabetical order
        returned_codes = [code for code, _ in lookups]
        expected_order = sorted([c.code for c in countries_random])
        assert returned_codes == expected_order

    def test_filter_integration_with_project_admin(
        self,
        project_admin: ProjectAdmin,
        projects_with_different_countries: list[Project],
    ) -> None:
        """Test that the filter is properly integrated with ProjectAdmin."""
        # Verify that ProjectCountryFilter is in the list_filter
        assert ProjectCountryFilter in project_admin.list_filter

    def test_filter_with_deleted_projects(
        self,
        country_filter: ProjectCountryFilter,
        request_factory: RequestFactory,
        project_admin: ProjectAdmin,
        user: User,
    ) -> None:
        """Test that filter works correctly when some projects are deleted."""
        # Create projects
        project1 = ProjectFactory.create(
            country="US",
            created_by=user.email,
        )

        _ = ProjectFactory.create(
            country="FR",
            created_by=user.email,
        )

        # Delete one project
        _ = project1.delete()

        request = request_factory.get("/admin/")
        lookups = country_filter.lookups(request, project_admin)

        # Should only return the country of the remaining project
        assert len(lookups) == 1
        assert lookups[0][0] == "FR"

    def test_filter_performance_with_large_dataset(
        self,
        country_filter: ProjectCountryFilter,
        request_factory: RequestFactory,
        project_admin: ProjectAdmin,
        user: User,
    ) -> None:
        """Test filter performance with a larger dataset."""
        # Create many projects with a few different countries
        countries_to_use = random.sample(list(countries), 3)
        countries_iter = cycle(countries_to_use)

        for _ in range(100):
            _ = ProjectFactory.create(
                country=next(countries_iter).code,
                created_by=user.email,
            )

        request = request_factory.get("/admin/")
        lookups = country_filter.lookups(request, project_admin)

        # Should still only return 3 distinct countries
        assert len(lookups) == 3  # noqa: PLR2004
        returned_codes = [code for code, _ in lookups]
        assert set(returned_codes) == {c.code for c in countries_to_use}
