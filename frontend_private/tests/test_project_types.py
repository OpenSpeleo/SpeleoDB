"""Software choices and conversion capabilities in project pages."""

from __future__ import annotations

import re

from django.test import TestCase
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.surveys.templatetags.project_types import get_project_type_color
from speleodb.surveys.templatetags.project_types import get_project_type_display
from speleodb.surveys.templatetags.project_types import get_project_types
from speleodb.users.tests.factories import UserFactory


class TestProjectTypePresentation(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = UserFactory.create()
        self.project = ProjectFactory.create(
            created_by=self.user.email, type=ProjectType.STALAGMIGHT
        )
        UserProjectPermissionFactory.create(
            target=self.user, project=self.project, level=PermissionLevel.ADMIN
        )
        self.client.force_login(self.user)

    def test_new_project_offers_stalagmight(self) -> None:
        response = self.client.get(reverse("private:project_new"))
        assert response.status_code == status.HTTP_200_OK
        assert '<option value="STALAGMIGHT">STALAGMIGHT</option>' in (
            response.content.decode()
        )

    def test_details_selects_stalagmight_and_explains_conversion(self) -> None:
        response = self.client.get(
            reverse("private:project_details", kwargs={"project_id": self.project.pk})
        )
        assert response.status_code == status.HTTP_200_OK
        html = response.content.decode()
        assert re.search(
            r'<option value="STALAGMIGHT"\s+selected\s*>STALAGMIGHT</option>', html
        )
        assert "Automatic map generation is not supported for this project type." in (
            html
        )

    def test_stalagmight_badges_render_on_mobile_and_desktop(self) -> None:
        response = self.client.get(reverse("private:projects"))
        assert response.status_code == status.HTTP_200_OK
        html = response.content.decode()
        badges = re.findall(
            r'<div class="[^"]*\bbg-teal-600\b[^"]*">\s*STALAGMIGHT\s*</div>',
            html,
        )
        assert len(badges) == 2  # noqa: PLR2004 - mobile card and desktop row

    @parameterized.expand([(project_type,) for project_type in ProjectType])
    def test_every_type_has_a_label_and_badge(self, project_type: ProjectType) -> None:
        assert project_type.label in get_project_types()
        assert get_project_type_display(project_type.value) == project_type.label
        assert get_project_type_color(project_type.value)
        if project_type != ProjectType.OTHER:
            assert get_project_type_color(project_type.value) != "bg-slate-500"

    @parameterized.expand([ProjectType.ARIANE, ProjectType.COMPASS])
    def test_supported_types_do_not_show_conversion_notice(
        self, project_type: ProjectType
    ) -> None:
        self.project.type = project_type
        self.project.save(update_fields=["type"])
        response = self.client.get(
            reverse("private:project_details", kwargs={"project_id": self.project.pk})
        )
        assert response.status_code == status.HTTP_200_OK
        assert "Automatic map generation is not supported" not in (
            response.content.decode()
        )
