from __future__ import annotations

from django.http import HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseUserTestCaseMixin
from speleodb.api.v2.tests.factories import GPSTrackFactory
from speleodb.api.v2.tests.factories import GPSTrackUserPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.users.tests.factories import UserFactory

RESPONSIVE_RENDER_COUNT = 2


class GPSTrackFrontendViewsTest(BaseUserTestCaseMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.track = GPSTrackFactory.create(user=self.user, name="Shared Traverse")

    def permission_url(self) -> str:
        return reverse(
            "private:gps_track_user_permissions",
            kwargs={"track_id": self.track.id},
        )

    def test_list_requires_authentication(self) -> None:
        response = self.client.get(reverse("private:gps_tracks"))

        assert response.status_code == status.HTTP_302_FOUND
        assert isinstance(response, HttpResponseRedirect)

    def test_permission_page_requires_authentication(self) -> None:
        response = self.client.get(self.permission_url())

        assert response.status_code == status.HTTP_302_FOUND
        assert isinstance(response, HttpResponseRedirect)

    def test_active_reader_can_view_collaborators_without_mutation_controls(
        self,
    ) -> None:
        reader = UserFactory.create(email="reader-gps@example.com")
        GPSTrackUserPermissionFactory.create(
            user=reader,
            gps_track=self.track,
            level=PermissionLevel.READ_ONLY,
        )
        self.client.force_login(reader)

        response = self.client.get(self.permission_url())

        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        assert self.user.email in content
        assert reader.email in content
        assert "Shared Traverse" in content
        assert "Grant Access" not in content
        assert "btn_open_edit_perm" not in content
        assert "btn_delete_perm" not in content
        assert 'data-speleodb-controller="permission-modal"' not in content
        assert 'id="permission_modal"' not in content

    def test_writer_can_view_collaborators_without_mutation_controls(self) -> None:
        writer = UserFactory.create(email="writer-gps@example.com")
        GPSTrackUserPermissionFactory.create(
            user=writer,
            gps_track=self.track,
            level=PermissionLevel.READ_AND_WRITE,
        )
        self.client.force_login(writer)

        response = self.client.get(self.permission_url())

        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        assert writer.email in content
        assert "Grant Access" not in content
        assert "btn_open_edit_perm" not in content
        assert "btn_delete_perm" not in content

    def test_admin_receives_modal_and_other_user_mutation_controls(self) -> None:
        collaborator = UserFactory.create(email="collaborator-gps@example.com")
        GPSTrackUserPermissionFactory.create(
            user=collaborator,
            gps_track=self.track,
            level=PermissionLevel.READ_AND_WRITE,
        )
        self.client.force_login(self.user)

        response = self.client.get(self.permission_url())

        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        assert "Grant Access" in content
        assert (
            content.count('class="cursor-pointer btn_open_edit_perm"')
            == RESPONSIVE_RENDER_COUNT
        )
        assert (
            content.count('class="cursor-pointer btn_delete_perm"')
            == RESPONSIVE_RENDER_COUNT
        )
        assert f'data-user="{collaborator.email}"' in content
        assert f'data-user="{self.user.email}"' not in content
        assert 'data-speleodb-controller="permission-modal"' in content
        assert 'id="permission_modal"' in content
        assert (
            reverse(
                "api:v2:gps-track-permissions",
                kwargs={"id": self.track.id},
            )
            in content
        )
        assert "Read Only" in content
        assert "Read And Write" in content
        assert "Admin" in content
        assert "Web Viewer" not in content

    def test_permissions_are_sorted_by_level_then_email(self) -> None:
        writer = UserFactory.create(email="a-writer-gps@example.com")
        reader = UserFactory.create(email="z-reader-gps@example.com")
        GPSTrackUserPermissionFactory.create(
            user=reader,
            gps_track=self.track,
            level=PermissionLevel.READ_ONLY,
        )
        GPSTrackUserPermissionFactory.create(
            user=writer,
            gps_track=self.track,
            level=PermissionLevel.READ_AND_WRITE,
        )
        self.client.force_login(self.user)

        content = self.client.get(self.permission_url()).content.decode()

        assert content.index(self.user.email) < content.index(writer.email)
        assert content.index(writer.email) < content.index(reader.email)

    def test_permission_page_excludes_revoked_and_other_track_permissions(self) -> None:
        active_user = UserFactory.create(email="active-gps@example.com")
        revoked_user = UserFactory.create(email="inactive-gps@example.com")
        other_user = UserFactory.create(email="other-track-gps@example.com")
        other_track = GPSTrackFactory.create(user=other_user)
        GPSTrackUserPermissionFactory.create(
            user=active_user,
            gps_track=self.track,
            level=PermissionLevel.READ_ONLY,
        )
        GPSTrackUserPermissionFactory.create(
            user=revoked_user,
            gps_track=self.track,
            level=PermissionLevel.READ_ONLY,
            is_active=False,
        )
        unrelated_user = UserFactory.create(email="unrelated-perm-gps@example.com")
        GPSTrackUserPermissionFactory.create(
            user=unrelated_user,
            gps_track=other_track,
            level=PermissionLevel.READ_ONLY,
        )
        self.client.force_login(self.user)

        content = self.client.get(self.permission_url()).content.decode()

        assert active_user.email in content
        assert revoked_user.email not in content
        assert unrelated_user.email not in content

    def test_revoked_stranger_and_inactive_track_redirect_to_listing(self) -> None:
        stranger = UserFactory.create(email="stranger-gps@example.com")
        self.client.force_login(stranger)

        response = self.client.get(self.permission_url())

        assert response.status_code == status.HTTP_302_FOUND
        assert response["Location"] == reverse("private:gps_tracks")

        collaborator = UserFactory.create(email="revoked-gps@example.com")
        permission = GPSTrackUserPermissionFactory.create(
            user=collaborator,
            gps_track=self.track,
            level=PermissionLevel.READ_ONLY,
            is_active=False,
        )
        self.client.force_login(collaborator)

        response = self.client.get(self.permission_url())

        assert not permission.is_active
        assert response.status_code == status.HTTP_302_FOUND
        assert response["Location"] == reverse("private:gps_tracks")

        self.track.is_active = False
        self.track.save(update_fields=["is_active", "modified_date"])
        self.client.force_login(self.user)
        response = self.client.get(self.permission_url())

        assert response.status_code == status.HTTP_302_FOUND
        assert response["Location"] == reverse("private:gps_tracks")

    def test_permission_page_escapes_track_and_user_names(self) -> None:
        self.track.name = '<script>alert("track")</script>'
        self.track.save(update_fields=["name", "modified_date"])
        self.user.name = '<img src=x onerror="alert(1)">'
        self.user.save(update_fields=["name"])
        self.client.force_login(self.user)

        content = self.client.get(self.permission_url()).content.decode()

        assert "&lt;script&gt;alert(&quot;track&quot;)&lt;/script&gt;" in content
        assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in content
        assert '<script>alert("track")</script>' not in content
        assert '<img src=x onerror="alert(1)">' not in content

    def test_list_declares_permission_aware_controller_and_shared_wording(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("private:gps_tracks"))

        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        assert "My GPS Tracks" in content
        assert "Refreshing GPS tracks..." in content
        assert "Refreshing map data..." not in content
        assert '<div class="font-semibold text-center">Owner</div>' in content
        assert '<div class="font-semibold text-center">Access Level</div>' in content
        assert 'data-speleodb-controller="gps-tracks"' in content
        assert reverse("api:v2:gps-tracks") in content
