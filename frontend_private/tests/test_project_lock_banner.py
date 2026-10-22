# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django.test import Client
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from frontend_private.tests.controller_context import controller_context
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.http import HttpResponseBase


EDITION_NOT_ENABLED_TEXT = "Project edition is not enabled."
ENABLE_EDITION_LINK_TEXT = "Enable Project Edition"
READONLY_NO_ACCESS_TEXT = "You do not have edit access to this project."
EDITED_BY_TEXT = "Currently being edited by"
EDITION_ENABLED_TEXT = "Project edition is enabled."
UPLOAD_LINK_TEXT = "Upload new Revision"

AMBER_BANNER_LINK_CLASS = "text-amber-400 underline"
EMERALD_BANNER_LINK_CLASS = "text-emerald-400 underline"


class ProjectLockBannerTestBase(TestCase):
    """Shared setup for lock-status banner tests."""

    def setUp(self) -> None:
        super().setUp()
        self.user = UserFactory.create()
        self.other_user = UserFactory.create()
        self.project = ProjectFactory.create(created_by=self.user.email)

    def _get_page(self, view_name: str, project_id: str | None = None) -> str:
        pid = project_id or str(self.project.id)
        url = reverse(f"private:{view_name}", kwargs={"project_id": pid})
        self.client.force_login(self.user)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        return response.content.decode()


class TestBannerNoLockWriteAccess(ProjectLockBannerTestBase):
    """State 1: No active lock, user has write access (READ_AND_WRITE or ADMIN)."""

    def setUp(self) -> None:
        super().setUp()
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )

    def test_unlocked_writer_can_enable_editing(self) -> None:
        html = self._get_page("project_details")
        assert EDITION_NOT_ENABLED_TEXT in html
        assert ENABLE_EDITION_LINK_TEXT in html
        assert EDITION_ENABLED_TEXT not in html

    def test_enable_edition_button_acquires_and_reloads_current_page(self) -> None:
        self.client = Client(enforce_csrf_checks=True)
        html: str = self._get_page("project_details")
        button: re.Match[str] | None = re.search(
            r'<button\b[^>]*id="btn_lock_project"[^>]*>', html
        )
        assert button is not None
        assert 'type="button"' in button.group()
        assert "href=" not in button.group()
        context = controller_context(html, "mutex-lock")
        assert context == {"projectId": str(self.project.id), "canAcquire": True}
        response: HttpResponseBase = self.client.post(
            reverse("api:v2:project-acquire", kwargs={"id": context["projectId"]}),
            content_type="application/json",
            headers={"X-CSRFToken": self.client.cookies["csrftoken"].value},
        )
        assert response.status_code == status.HTTP_200_OK
        self.project.refresh_from_db()
        assert self.project.mutex_owner == self.user
        reloaded_html: str = self._get_page("project_details")
        assert EDITION_ENABLED_TEXT in reloaded_html
        assert UPLOAD_LINK_TEXT in reloaded_html
        assert 'id="btn_lock_project"' not in reloaded_html

    def test_banner_acquisition_requires_csrf(self) -> None:
        self.client = Client(enforce_csrf_checks=True)
        self._get_page("project_details")
        response: HttpResponseBase = self.client.post(
            reverse("api:v2:project-acquire", kwargs={"id": self.project.id}),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        self.project.refresh_from_db()
        assert self.project.active_mutex is None

    def test_acquisition_preserves_a_lock_taken_after_page_load(self) -> None:
        self._get_page("project_details")
        UserProjectPermissionFactory.create(
            target=self.other_user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )
        self.project.acquire_mutex(user=self.other_user)
        response: HttpResponseBase = self.client.post(
            reverse("api:v2:project-acquire", kwargs={"id": self.project.id}),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.project.refresh_from_db()
        assert self.project.mutex_owner == self.other_user


class TestBannerNoLockReadOnly(ProjectLockBannerTestBase):
    """State 2: No active lock, user has read-only access."""

    def setUp(self) -> None:
        super().setUp()
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_ONLY,
        )

    def test_readonly_user_has_no_acquisition_action(self) -> None:
        html = self._get_page("project_details")
        assert READONLY_NO_ACCESS_TEXT in html
        assert ENABLE_EDITION_LINK_TEXT not in html
        assert 'data-speleodb-controller="mutex-lock"' not in html

    def test_readonly_user_cannot_acquire_via_api(self) -> None:
        self._get_page("project_details")
        response: HttpResponseBase = self.client.post(
            reverse("api:v2:project-acquire", kwargs={"id": self.project.id}),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        self.project.refresh_from_db()
        assert self.project.active_mutex is None


class TestBannerLockedByOtherUser(ProjectLockBannerTestBase):
    """State 3: Project locked by another user -- current user sees read-only."""

    def setUp(self) -> None:
        super().setUp()
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )
        UserProjectPermissionFactory.create(
            target=self.other_user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )
        self.project.acquire_mutex(user=self.other_user)

    def test_other_owner_is_visible_without_upload_action(self) -> None:
        html = self._get_page("project_details")
        assert EDITED_BY_TEXT in html
        assert self.other_user.name in html
        assert ENABLE_EDITION_LINK_TEXT not in html
        upload_url = reverse(
            "private:project_upload", kwargs={"project_id": self.project.id}
        )
        assert upload_url not in html


class TestBannerLockedByCurrentUser(ProjectLockBannerTestBase):
    """State 4: Project locked by the current user -- editing enabled."""

    def setUp(self) -> None:
        super().setUp()
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )
        self.project.acquire_mutex(user=self.user)

    def test_owner_can_upload_without_acquisition_action(self) -> None:
        html = self._get_page("project_details")
        assert EDITION_ENABLED_TEXT in html
        assert UPLOAD_LINK_TEXT in html
        expected_url = reverse(
            "private:project_upload", kwargs={"project_id": self.project.id}
        )
        assert expected_url in html
        assert ENABLE_EDITION_LINK_TEXT not in html
        assert READONLY_NO_ACCESS_TEXT not in html


class TestConditionalLinkHiding(ProjectLockBannerTestBase):
    """Links should be hidden when already on the target page."""

    def setUp(self) -> None:
        super().setUp()
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )

    def test_no_enable_edition_link_on_mutex_page(self) -> None:
        """'Enable Project Edition' banner link must not appear on Lock Management."""
        html = self._get_page("project_mutexes")
        assert EDITION_NOT_ENABLED_TEXT in html
        assert AMBER_BANNER_LINK_CLASS not in html

    def test_enable_edition_link_present_on_other_pages(self) -> None:
        """'Enable Project Edition' banner link must appear on non-mutex pages."""
        for view_name in ("project_details", "project_user_permissions"):
            html = self._get_page(view_name)
            assert AMBER_BANNER_LINK_CLASS in html, (
                f"Banner link missing on {view_name}"
            )
            assert ENABLE_EDITION_LINK_TEXT in html, f"Link text missing on {view_name}"

    def test_no_upload_link_on_upload_page(self) -> None:
        """'Upload new Revision' banner link must not appear on the Upload page."""
        self.project.acquire_mutex(user=self.user)
        html = self._get_page("project_upload")
        assert EDITION_ENABLED_TEXT in html
        assert EMERALD_BANNER_LINK_CLASS not in html

    def test_upload_link_present_on_other_pages(self) -> None:
        """'Upload new Revision' banner link must appear on non-upload pages."""
        self.project.acquire_mutex(user=self.user)
        for view_name in ("project_details", "project_user_permissions"):
            html = self._get_page(view_name)
            assert EMERALD_BANNER_LINK_CLASS in html, (
                f"Banner link missing on {view_name}"
            )
            assert UPLOAD_LINK_TEXT in html, f"Link text missing on {view_name}"


class TestBannerConsistencyAcrossPages(ProjectLockBannerTestBase):
    """The correct banner must appear on every project sub-page."""

    def setUp(self) -> None:
        super().setUp()
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.ADMIN,
        )

    SUBPAGES: list[str] = [
        "project_details",
        "project_user_permissions",
        "project_team_permissions",
        "project_mutexes",
        "project_revisions",
        "project_git_instructions",
        "project_danger_zone",
    ]

    def test_amber_banner_on_all_subpages_when_unlocked(self) -> None:
        for view_name in self.SUBPAGES:
            html = self._get_page(view_name)
            assert EDITION_NOT_ENABLED_TEXT in html, (
                f"Edition-not-enabled text missing on {view_name}"
            )
            assert html.count('id="btn_lock_project"') == 1, view_name
            assert html.count('data-speleodb-controller="mutex-lock"') == 1, view_name
            context = controller_context(html, "mutex-lock")
            assert context["projectId"] == str(self.project.id), view_name
            assert context["canAcquire"] is True, view_name
            assert context.get("canRelease", False) is (
                view_name == "project_mutexes"
            ), view_name
            assert html.count('id="modal_error"') == 1, view_name
            assert 'name="csrfmiddlewaretoken"' in html, view_name
