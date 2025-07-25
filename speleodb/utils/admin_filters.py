# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Generic
from typing import TypeVar

from django.contrib import admin
from django.db.models import Model
from django_countries import countries

from speleodb.surveys.models import Project
from speleodb.surveys.models import Station
from speleodb.users.models import SurveyTeam
from speleodb.users.models import User

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

T = TypeVar("T", bound=Model)


class BaseCountryFilter(Generic[T], admin.SimpleListFilter, ABC):  # noqa: UP046
    """Custom filter that shows only countries actually used by objects."""

    title = "Country"
    parameter_name = "country"

    @abstractmethod
    def get_used_countries(self) -> list[str]:
        """Get the countries actually used by the objects."""
        raise NotImplementedError

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin[T]
    ) -> list[tuple[str, str]]:
        """Return only countries that are actually used by projects."""
        # Get distinct countries from projects, ordered alphabetically
        used_countries = self.get_used_countries()

        # Convert country codes to (code, name) tuples
        country_choices: list[tuple[str, str]] = []
        for country_code in used_countries:
            country_name = dict(countries)[country_code]
            country_choices.append((country_code, country_name))

        return country_choices

    def queryset(self, request: HttpRequest, queryset: QuerySet[T]) -> QuerySet[T]:
        """Filter queryset based on selected country."""
        if self.value():
            return queryset.filter(country=self.value())
        return queryset


class ProjectCountryFilter(BaseCountryFilter[Project]):
    """Custom filter that shows only countries actually used by projects."""

    def get_used_countries(self) -> list[str]:
        """Return only countries that are actually used by projects."""
        # Get distinct countries from projects, ordered alphabetically
        return list(
            Project.objects.values_list("country", flat=True)
            .distinct()
            .order_by("country")
        )


class SurveyTeamCountryFilter(BaseCountryFilter[SurveyTeam]):
    """Custom filter that shows only countries actually used by users."""

    def get_used_countries(self) -> list[str]:
        """Return only countries that are actually used by projects."""
        # Get distinct countries from projects, ordered alphabetically
        return list(
            SurveyTeam.objects.values_list("country", flat=True)
            .distinct()
            .order_by("country")
        )


class UserCountryFilter(BaseCountryFilter[User]):
    """Custom filter that shows only countries actually used by users."""

    def get_used_countries(self) -> list[str]:
        """Return only countries that are actually used by projects."""
        # Get distinct countries from projects, ordered alphabetically
        return list(
            User.objects.values_list("country", flat=True)
            .distinct()
            .order_by("country")
        )


class BaseProjectFilter(Generic[T], admin.SimpleListFilter, ABC):  # noqa: UP046
    """Custom filter that shows only countries actually used by objects."""

    title = "Project"
    parameter_name = "project"

    @abstractmethod
    def get_used_projects(self) -> list[Project]:
        """Get the projects actually used by the objects."""
        raise NotImplementedError

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin[T]
    ) -> list[tuple[str, str]]:
        """Return only countries that are actually used by projects."""
        # Get distinct countries from projects, ordered alphabetically
        used_projects = self.get_used_projects()

        # Convert Projects to (id, name) tuples
        return [(str(project.id), project.name) for project in used_projects]

    def queryset(self, request: HttpRequest, queryset: QuerySet[T]) -> QuerySet[T]:
        """Filter queryset based on selected country."""
        if self.value():
            return queryset.filter(project=self.value())
        return queryset


class StationProjectFilter(BaseProjectFilter[Station]):
    """Custom filter that shows only countries actually used by users."""

    def get_used_projects(self) -> list[Project]:
        """Return only countries that are actually used by projects."""
        # Get distinct countries from projects, ordered alphabetically
        return list(Project.objects.filter(rel_stations__isnull=False).order_by("name"))
