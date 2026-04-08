# -*- coding: utf-8 -*-

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.users.tests.factories import UserFactory

AMBER_BORDER = "border-amber-500/60"
SLATE_BORDER = "border-slate-500/50"
SKY_BORDER = "border-sky-500/60"
EMERALD_BORDER = "border-emerald-500/60"

EDITION_NOT_ENABLED_TEXT = "Project edition is not enabled."
ENABLE_EDITION_LINK_TEXT = "Enable Project Edition"
READONLY_NO_ACCESS_TEXT = "You do not have edit access to this project."
EDITED_BY_TEXT = "Currently being edited by"
EDITION_ENABLED_TEXT = "Project edition is enabled."
UPLOAD_LINK_TEXT = "Upload new Revision"
EDITING_BADGE = "Editing"
READONLY_BADGE_MARKUP = 'class="shrink-0 rounded-full bg-sky-500/20'

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

    def test_amber_banner_is_shown(self) -> None:
        html = self._get_page("project_details")
        assert AMBER_BORDER in html

    def test_edition_not_enabled_text_present(self) -> None:
        html = self._get_page("project_details")
        assert EDITION_NOT_ENABLED_TEXT in html

    def test_enable_edition_link_present(self) -> None:
        html = self._get_page("project_details")
        assert ENABLE_EDITION_LINK_TEXT in html

    def test_enable_edition_link_points_to_mutex_page(self) -> None:
        html = self._get_page("project_details")
        expected_url = reverse(
            "private:project_mutexes", kwargs={"project_id": self.project.id}
        )
        assert expected_url in html

    def test_no_emerald_banner(self) -> None:
        html = self._get_page("project_details")
        assert EMERALD_BORDER not in html

    def test_no_sky_banner(self) -> None:
        html = self._get_page("project_details")
        assert SKY_BORDER not in html

    def test_no_slate_banner(self) -> None:
        html = self._get_page("project_details")
        assert SLATE_BORDER not in html


class TestBannerNoLockReadOnly(ProjectLockBannerTestBase):
    """State 2: No active lock, user has read-only access."""

    def setUp(self) -> None:
        super().setUp()
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_ONLY,
        )

    def test_slate_banner_is_shown(self) -> None:
        html = self._get_page("project_details")
        assert SLATE_BORDER in html

    def test_readonly_text_present(self) -> None:
        html = self._get_page("project_details")
        assert READONLY_NO_ACCESS_TEXT in html

    def test_no_enable_edition_link(self) -> None:
        html = self._get_page("project_details")
        assert ENABLE_EDITION_LINK_TEXT not in html

    def test_no_amber_banner(self) -> None:
        html = self._get_page("project_details")
        assert AMBER_BORDER not in html

    def test_no_emerald_banner(self) -> None:
        html = self._get_page("project_details")
        assert EMERALD_BORDER not in html

    def test_no_sky_banner(self) -> None:
        html = self._get_page("project_details")
        assert SKY_BORDER not in html


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

    def test_sky_banner_is_shown(self) -> None:
        html = self._get_page("project_details")
        assert SKY_BORDER in html

    def test_edited_by_text_present(self) -> None:
        html = self._get_page("project_details")
        assert EDITED_BY_TEXT in html

    def test_other_user_name_shown(self) -> None:
        html = self._get_page("project_details")
        assert self.other_user.name in html

    def test_readonly_badge_present(self) -> None:
        html = self._get_page("project_details")
        assert READONLY_BADGE_MARKUP in html

    def test_no_amber_banner(self) -> None:
        html = self._get_page("project_details")
        assert AMBER_BORDER not in html

    def test_no_emerald_banner(self) -> None:
        html = self._get_page("project_details")
        assert EMERALD_BORDER not in html

    def test_no_upload_link(self) -> None:
        html = self._get_page("project_details")
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

    def test_emerald_banner_is_shown(self) -> None:
        html = self._get_page("project_details")
        assert EMERALD_BORDER in html

    def test_edition_enabled_text_present(self) -> None:
        html = self._get_page("project_details")
        assert EDITION_ENABLED_TEXT in html

    def test_upload_link_present(self) -> None:
        html = self._get_page("project_details")
        assert UPLOAD_LINK_TEXT in html

    def test_upload_link_points_to_upload_page(self) -> None:
        html = self._get_page("project_details")
        expected_url = reverse(
            "private:project_upload", kwargs={"project_id": self.project.id}
        )
        assert expected_url in html

    def test_editing_badge_present(self) -> None:
        html = self._get_page("project_details")
        assert EDITING_BADGE in html

    def test_no_amber_banner(self) -> None:
        html = self._get_page("project_details")
        assert AMBER_BORDER not in html

    def test_no_sky_banner(self) -> None:
        html = self._get_page("project_details")
        assert SKY_BORDER not in html

    def test_no_readonly_text(self) -> None:
        html = self._get_page("project_details")
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
            assert AMBER_BORDER in html, f"Amber banner missing on {view_name}"
            assert EDITION_NOT_ENABLED_TEXT in html, (
                f"Edition-not-enabled text missing on {view_name}"
            )

    def test_emerald_banner_on_all_subpages_when_editing(self) -> None:
        self.project.acquire_mutex(user=self.user)
        for view_name in self.SUBPAGES:
            html = self._get_page(view_name)
            assert EMERALD_BORDER in html, f"Emerald banner missing on {view_name}"
            assert EDITION_ENABLED_TEXT in html, (
                f"Edition-enabled text missing on {view_name}"
            )

    def test_sky_banner_on_all_subpages_when_locked_by_other(self) -> None:
        UserProjectPermissionFactory.create(
            target=self.other_user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )
        self.project.acquire_mutex(user=self.other_user)
        for view_name in self.SUBPAGES:
            html = self._get_page(view_name)
            assert SKY_BORDER in html, f"Sky banner missing on {view_name}"
            assert self.other_user.name in html, (
                f"Other user name missing on {view_name}"
            )
