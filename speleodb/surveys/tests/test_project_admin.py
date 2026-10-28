"""The model-owned project software choice propagates to Django admin."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.common.enums import ProjectType
from speleodb.common.enums import ProjectVisibility
from speleodb.surveys.models import Project

if TYPE_CHECKING:
    from django.test import Client


def test_project_admin_adds_and_filters_stalagmight(admin_client: Client) -> None:
    add_url = reverse("admin:surveys_project_add")
    form_response = admin_client.get(add_url)
    assert form_response.status_code == status.HTTP_200_OK
    assert ("stalagmight", "STALAGMIGHT") in (
        form_response.context["adminform"].form.fields["type"].choices
    )
    response = admin_client.post(
        add_url,
        data={
            "name": "Stalagmight admin survey",
            "description": "Added through Django admin",
            "country": "US",
            "type": "stalagmight",
            "color": "#0d9488",
            "visibility": ProjectVisibility.PRIVATE,
            "is_active": "on",
        },
    )
    assert response.status_code == status.HTTP_302_FOUND
    project = Project.objects.get(name="Stalagmight admin survey")
    assert project.type == ProjectType.STALAGMIGHT
    ProjectFactory.create(type=ProjectType.COMPASS, name="Unrelated Compass survey")
    filtered = admin_client.get(
        reverse("admin:surveys_project_changelist"), {"type__exact": "stalagmight"}
    )
    assert filtered.status_code == status.HTTP_200_OK
    assert list(filtered.context["cl"].queryset.values_list("pk", flat=True)) == [
        project.pk
    ]


def test_project_admin_changes_software_to_stalagmight(admin_client: Client) -> None:
    project = ProjectFactory.create(type=ProjectType.ARIANE)
    url = reverse("admin:surveys_project_change", kwargs={"object_id": project.pk})
    response = admin_client.post(
        url,
        data={
            "name": project.name,
            "description": project.description,
            "country": "US",
            "type": "stalagmight",
            "color": project.color,
            "visibility": ProjectVisibility.PRIVATE,
            "is_active": "on",
        },
    )
    assert response.status_code == status.HTTP_302_FOUND
    project.refresh_from_db()
    assert project.type == ProjectType.STALAGMIGHT
    change_response = admin_client.get(url)
    assert change_response.status_code == status.HTTP_200_OK
    assert change_response.context["adminform"].form["type"].value() == "stalagmight"
