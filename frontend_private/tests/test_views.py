from __future__ import annotations

import hashlib
import random
from typing import TYPE_CHECKING
from typing import Any

from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse
from parameterized.parameterized import parameterized
from parameterized.parameterized import parameterized_class
from rest_framework import status
from rest_framework.authtoken.models import Token

from speleodb.api.v2.tests.base_testcase import BaseProjectTestCaseMixin
from speleodb.api.v2.tests.base_testcase import BaseUserTestCaseMixin
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import CylinderFleetFactory
from speleodb.api.v2.tests.factories import CylinderFleetUserPermissionFactory
from speleodb.api.v2.tests.factories import LandmarkCollectionFactory
from speleodb.api.v2.tests.factories import LandmarkCollectionUserPermissionFactory
from speleodb.api.v2.tests.factories import LandmarkFactory
from speleodb.api.v2.tests.factories import SensorFleetFactory
from speleodb.api.v2.tests.factories import SensorFleetUserPermissionFactory
from speleodb.api.v2.tests.factories import SurveyTeamFactory
from speleodb.api.v2.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import SurveyTeamMembershipRole
from speleodb.gis.landmark_collections import get_or_create_personal_landmark_collection
from speleodb.gis.models import GISView
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.users.models import SurveyTeam


class BaseTestCase(BaseUserTestCaseMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()

    def execute_test(
        self,
        view_name: str,
        kwargs: Any | None = None,
        expected_status: int = status.HTTP_200_OK,
    ) -> None:
        url = reverse(f"private:{view_name}", kwargs=kwargs)

        self.client.force_login(self.user)
        response = self.client.get(url)

        if expected_status != status.HTTP_302_FOUND:
            assert isinstance(response, HttpResponse), type(response)
        else:
            assert isinstance(response, HttpResponseRedirect), type(response)

        assert response.status_code == expected_status

        assert response["Content-Type"].startswith("text/html"), response[
            "Content-Type"
        ]


class UserViewsTest(BaseTestCase):
    @parameterized.expand(
        [
            "user_dashboard",
            "user_profile",
            "user_authtoken",
            "user_feedback",
            "user_password",
            "user_preferences",
        ]
    )
    def test_view_with_no_args(self, view_name: str) -> None:
        self.execute_test(view_name)


@parameterized_class(
    ("role"), [(SurveyTeamMembershipRole.LEADER,), (SurveyTeamMembershipRole.MEMBER,)]
)
class TeamViewsTest(BaseTestCase):
    role: SurveyTeamMembershipRole

    def setUp(self) -> None:
        super().setUp()

        self.team: SurveyTeam = SurveyTeamFactory.create()

        # Must make the user is at least a member of the team - one of each
        _ = SurveyTeamMembershipFactory(team=self.team, user=self.user, role=self.role)

    @parameterized.expand(["teams", "team_new"])
    def test_view_with_no_args(self, view_name: str) -> None:
        self.execute_test(view_name)

    @parameterized.expand(["team_details", "team_memberships", "team_danger_zone"])
    def test_view_with_team_id(self, view_name: str) -> None:
        expected_status = (
            status.HTTP_200_OK
            if self.role == SurveyTeamMembershipRole.LEADER
            or view_name != "team_danger_zone"
            else status.HTTP_302_FOUND
        )
        self.execute_test(
            view_name, {"team_id": self.team.id}, expected_status=expected_status
        )


@parameterized_class(
    ("level", "permission_type"),
    [
        (PermissionLevel.READ_ONLY, PermissionType.USER),
        (PermissionLevel.READ_ONLY, PermissionType.TEAM),
        (PermissionLevel.READ_AND_WRITE, PermissionType.USER),
        (PermissionLevel.READ_AND_WRITE, PermissionType.TEAM),
        (PermissionLevel.ADMIN, PermissionType.USER),
    ],
)
class ProjectViewsTest(BaseProjectTestCaseMixin, BaseTestCase):
    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()

        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )

    @parameterized.expand(["projects", "project_new"])
    def test_view_with_no_args(self, view_name: str) -> None:
        self.execute_test(view_name)

    @parameterized.expand(
        [
            "project_details",
            "project_user_permissions",
            "project_team_permissions",
            "project_mutexes",
            "project_revisions",
            "project_git_instructions",
            "project_danger_zone",
        ]
    )
    def test_view_with_project_id(self, view_name: str) -> None:
        expected_status = (
            status.HTTP_200_OK
            if self.level == PermissionLevel.ADMIN or view_name != "project_danger_zone"
            else status.HTTP_302_FOUND
        )

        self.execute_test(
            view_name, {"project_id": self.project.id}, expected_status=expected_status
        )

    @parameterized.expand([True, False, None])
    def test_view_with_project_id_and_maybe_lock(
        self, project_is_locked: bool | None
    ) -> None:
        """`project_is_locked` can take 3 values:
        - True: Yes the project is locked by the user
        - False: No the project is not locked by the user and by no-one else.
        - None: The project is locked by a different user.
        """

        expected_status: int
        match project_is_locked:
            case True:
                if self.level in [
                    PermissionLevel.WEB_VIEWER,
                    PermissionLevel.READ_ONLY,
                ]:
                    return  # this user can not acquire the lock

                self.project.acquire_mutex(self.user)
                expected_status = status.HTTP_200_OK

            case False:
                expected_status = status.HTTP_302_FOUND

            case None:
                # somebody has acquired the lock
                user = UserFactory.create()
                _ = UserProjectPermissionFactory(
                    target=user,
                    level=PermissionLevel.READ_AND_WRITE,
                    project=self.project,
                )
                self.project.acquire_mutex(user)
                expected_status = status.HTTP_302_FOUND
            case _:
                raise ValueError(
                    f"Unexpected value for `project_is_locked`: {project_is_locked}"
                )

        self.execute_test(
            "project_upload",
            {"project_id": self.project.id},
            expected_status=expected_status,
        )

    def test_view_with_project_id_and_gitsha(self) -> None:
        self.execute_test(
            "project_revision_explorer",
            {
                "project_id": self.project.id,
                "hexsha": hashlib.sha1(
                    str(random.random()).encode("utf-8"),
                    usedforsecurity=False,
                ).hexdigest(),
            },
        )


class SensorFleetViewsTest(BaseTestCase):
    """Tests for Sensor Fleet frontend views."""

    def setUp(self) -> None:
        super().setUp()
        # Create a sensor fleet with user permission

        self.fleet = SensorFleetFactory.create()
        SensorFleetUserPermissionFactory.create(
            user=self.user,
            sensor_fleet=self.fleet,
            level=PermissionLevel.READ_ONLY,
        )

    @parameterized.expand(
        [
            "sensor_fleets",
            "sensor_fleet_new",
        ]
    )
    def test_view_with_no_args(self, view_name: str) -> None:
        self.execute_test(view_name)

    @parameterized.expand(
        [
            "sensor_fleet_details",
            "sensor_fleet_history",
            "sensor_fleet_user_permissions",
        ]
    )
    def test_view_with_fleet_id(self, view_name: str) -> None:
        self.execute_test(
            view_name,
            {"fleet_id": self.fleet.id},
        )


class CylinderFleetViewsTest(BaseTestCase):
    """Tests for Cylinder Fleet frontend views."""

    def setUp(self) -> None:
        super().setUp()
        self.fleet = CylinderFleetFactory.create()
        CylinderFleetUserPermissionFactory.create(
            user=self.user,
            cylinder_fleet=self.fleet,
            level=PermissionLevel.READ_ONLY,
        )

    @parameterized.expand(
        [
            "cylinder_fleets",
            "cylinder_fleet_new",
        ]
    )
    def test_view_with_no_args(self, view_name: str) -> None:
        self.execute_test(view_name)

    @parameterized.expand(
        [
            "cylinder_fleet_details",
            "cylinder_fleet_history",
            "cylinder_fleet_user_permissions",
        ]
    )
    def test_view_with_fleet_id(self, view_name: str) -> None:
        self.execute_test(
            view_name,
            {"fleet_id": self.fleet.id},
        )


class LandmarkCollectionViewsTest(BaseTestCase):
    """Tests for Landmark Collection frontend views."""

    def setUp(self) -> None:
        super().setUp()
        # ``TokenFactory`` already produces a 40-char hex key matching
        # the ``<user_token:key>`` converter; no manual swap needed.
        self.collection = LandmarkCollectionFactory.create(created_by=self.user.email)
        LandmarkCollectionUserPermissionFactory.create(
            user=self.user,
            collection=self.collection,
            level=PermissionLevel.READ_ONLY,
        )

    @parameterized.expand(
        [
            "landmark_collections",
            "landmark_collection_new",
        ]
    )
    def test_view_with_no_args(self, view_name: str) -> None:
        self.execute_test(view_name)

    @parameterized.expand(
        [
            "landmark_collection_details",
            "landmark_collection_user_permissions",
            "landmark_collection_gis_integration",
            "landmark_collection_danger_zone",
        ]
    )
    def test_view_with_collection_id(self, view_name: str) -> None:
        expected_status = (
            status.HTTP_302_FOUND
            if view_name == "landmark_collection_danger_zone"
            else status.HTTP_200_OK
        )

        self.execute_test(
            view_name,
            {"collection_id": self.collection.id},
            expected_status=expected_status,
        )

    def test_details_view_renders_landmark_table_and_export_links(self) -> None:
        LandmarkFactory.create(
            collection=self.collection,
            owner=self.user,
            name="Main Entrance",
            latitude="45.1234567",
            longitude="-122.1234567",
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "private:landmark_collection_details",
                kwargs={"collection_id": self.collection.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode()
        assert "collection_landmarks_table" in content
        assert "#collection_landmarks_table thead th" in content
        assert "text-align: center !important;" in content
        assert '<th class="px-4 py-3 text-center">Name</th>' in content
        assert '<th class="px-4 py-3 text-center">Created By</th>' in content
        assert '<td class="px-4 py-3 text-center">' in content
        assert '<td class="px-4 py-3 text-center text-sm text-slate-300">' in content
        assert "Main Entrance" in content
        assert "-122.1234567" in content
        assert "45.1234567" in content
        assert self.user.email in content
        assert "/private/map_viewer/?goto=45.1234567,-122.1234567" in content
        assert (
            reverse(
                "api:v2:landmark-collection-landmarks-export-excel",
                kwargs={"collection_id": self.collection.id},
            )
            in content
        )
        assert (
            reverse(
                "api:v2:landmark-collection-landmarks-export-gpx",
                kwargs={"collection_id": self.collection.id},
            )
            in content
        )

    def test_details_view_renders_empty_landmark_table_state(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "private:landmark_collection_details",
                kwargs={"collection_id": self.collection.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        assert "No landmarks in this collection yet" in response.content.decode()

    def test_listing_shows_personal_collection_management_row(self) -> None:
        personal_collection = get_or_create_personal_landmark_collection(user=self.user)

        self.client.force_login(self.user)
        response = self.client.get(reverse("private:landmark_collections"))

        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        assert self.collection.name in content
        assert str(personal_collection.id) in content
        assert personal_collection.name in content
        assert "Private" in content

    def test_listing_shows_landmark_count_column(self) -> None:
        for i in range(3):
            LandmarkFactory.create(
                collection=self.collection,
                owner=self.user,
                name=f"LM {i}",
                latitude=str(45 + i),
                longitude=str(-122 + i),
            )

        self.client.force_login(self.user)
        response = self.client.get(reverse("private:landmark_collections"))

        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        assert '<div class="font-semibold text-center">Landmarks</div>' in content

        rows = content.split("<tr>")
        collection_row = next(r for r in rows if self.collection.name in r)
        assert ">3<" in collection_row

    def test_listing_shows_zero_landmark_count_for_empty_collection(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("private:landmark_collections"))

        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK

        rows = content.split("<tr>")
        collection_row = next(r for r in rows if self.collection.name in r)
        assert ">0<" in collection_row

    def test_listing_shows_all_landmark_collections_gis_card(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("private:landmark_collections"))

        user_token = Token.objects.get(user=self.user)
        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        assert "All Landmark Collections GIS" in content
        assert "all active Landmark Collections you can read" in content
        assert "Sharing this link grants read access" in content
        assert 'id="landmark-collections-refresh-token-form"' in content
        assert "Refresh Application Token?" in content
        assert "Ariane, Compass, the mobile app" in content
        assert "any other connected app" in content
        assert (
            reverse(
                "api:v2:gis-ogc:landmark-collections-user-landing",
                kwargs={"key": user_token.key},
            )
            in content
        )
        assert 'id="landmark-collections-copy-btn"' in content

    def test_listing_refreshes_application_token(self) -> None:
        old_token_key = self.token.key

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("private:landmark_collections"),
            {"_refresh_user_token": "1"},
        )

        new_token = Token.objects.get(user=self.user)
        assert response.status_code == status.HTTP_302_FOUND
        assert isinstance(response, HttpResponseRedirect)
        assert response.url == reverse("private:landmark_collections")
        assert new_token.key != old_token_key
        assert not Token.objects.filter(key=old_token_key).exists()

    def test_listing_escapes_collection_names_and_descriptions(self) -> None:
        unsafe_collection = LandmarkCollectionFactory.create(
            name='<script>alert("name")</script>',
            description='<img src=x onerror="alert(1)">',
            created_by=self.user.email,
        )
        LandmarkCollectionUserPermissionFactory.create(
            user=self.user,
            collection=unsafe_collection,
            level=PermissionLevel.READ_ONLY,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("private:landmark_collections"))

        content = response.content.decode()
        assert "&lt;script&gt;alert(&quot;name&quot;)&lt;/script&gt;" in content
        assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in content
        assert '<script>alert("name")</script>' not in content
        assert '<img src=x onerror="alert(1)">' not in content

    def test_personal_collection_details_page_hides_shared_management(self) -> None:
        personal_collection = get_or_create_personal_landmark_collection(user=self.user)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "private:landmark_collection_details",
                kwargs={"collection_id": personal_collection.id},
            )
        )

        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        assert "Private" in content
        assert "User Access Control" not in content
        assert "GIS Integration" in content
        assert "Danger Zone" not in content
        assert "Collection Settings" not in content
        assert 'id="landmark_collection_details_form"' not in content
        assert 'id="name"' not in content
        assert 'id="description"' not in content
        assert 'id="color-picker-btn"' not in content
        assert 'name="color"' not in content
        assert "collection_landmarks_table" in content
        assert (
            reverse(
                "api:v2:landmark-collection-landmarks-export-excel",
                kwargs={"collection_id": personal_collection.id},
            )
            in content
        )
        assert (
            reverse(
                "api:v2:landmark-collection-landmarks-export-gpx",
                kwargs={"collection_id": personal_collection.id},
            )
            in content
        )

    def test_personal_collection_gis_page_shows_endpoint(self) -> None:
        personal_collection = get_or_create_personal_landmark_collection(user=self.user)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "private:landmark_collection_gis_integration",
                kwargs={"collection_id": personal_collection.id},
            )
        )

        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        assert "GIS Integration" in content
        assert (
            reverse(
                "api:v2:gis-ogc:landmark-collection-landing",
                kwargs={"gis_token": personal_collection.gis_token},
            )
            in content
        )

    def test_personal_collection_gis_page_refreshes_token(self) -> None:
        personal_collection = get_or_create_personal_landmark_collection(user=self.user)
        old_token = personal_collection.gis_token

        self.client.force_login(self.user)
        response = self.client.post(
            reverse(
                "private:landmark_collection_gis_integration",
                kwargs={"collection_id": personal_collection.id},
            ),
            {"_refresh_token": "1"},
        )

        assert response.status_code == status.HTTP_302_FOUND
        assert isinstance(response, HttpResponseRedirect)
        assert response.url == reverse(
            "private:landmark_collection_gis_integration",
            kwargs={"collection_id": personal_collection.id},
        )
        personal_collection.refresh_from_db()
        assert personal_collection.gis_token != old_token

    def test_shared_collection_permissions_match_project_action_design(self) -> None:
        self.collection.permissions.filter(user=self.user).update(
            level=PermissionLevel.ADMIN,
        )
        collaborator = UserFactory.create()
        LandmarkCollectionUserPermissionFactory.create(
            user=collaborator,
            collection=self.collection,
            level=PermissionLevel.READ_AND_WRITE,
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "private:landmark_collection_user_permissions",
                kwargs={"collection_id": self.collection.id},
            )
        )

        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        assert "permissions-cards" in content
        assert "permissions-table bg-slate-800 shadow-lg rounded-sm" in content
        assert "Grant Access" in content
        assert "btn bg-slate-700 hover:bg-slate-600 text-slate-200" not in content
        assert "Remove" not in content
        assert "icon-tabler-lock-open" in content
        assert "icon-tabler-x" in content
        assert 'class="cursor-pointer btn_open_edit_perm"' in content
        assert 'class="cursor-pointer btn_delete_perm"' in content
        assert f'data-user="{collaborator.email}"' in content
        assert "modal_user_landmark_collection_permission_form" not in content
        assert "Select an option ..." in content

    def test_shared_collection_permissions_match_project_sorting(self) -> None:
        admin_user = UserFactory.create(email="z-admin@example.com")
        writer_user = UserFactory.create(email="a-writer@example.com")
        reader_user = UserFactory.create(email="m-reader@example.com")
        self.collection.permissions.filter(user=self.user).update(
            level=PermissionLevel.ADMIN,
        )
        LandmarkCollectionUserPermissionFactory.create(
            user=reader_user,
            collection=self.collection,
            level=PermissionLevel.READ_ONLY,
        )
        LandmarkCollectionUserPermissionFactory.create(
            user=admin_user,
            collection=self.collection,
            level=PermissionLevel.ADMIN,
        )
        LandmarkCollectionUserPermissionFactory.create(
            user=writer_user,
            collection=self.collection,
            level=PermissionLevel.READ_AND_WRITE,
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "private:landmark_collection_user_permissions",
                kwargs={"collection_id": self.collection.id},
            )
        )

        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        admin_position = content.index(admin_user.email)
        writer_position = content.index(writer_user.email)
        reader_position = content.index(reader_user.email)
        assert admin_position < writer_position < reader_position

    @parameterized.expand(
        [
            "landmark_collection_user_permissions",
            "landmark_collection_danger_zone",
        ]
    )
    def test_personal_collection_management_subpages_redirect(
        self,
        view_name: str,
    ) -> None:
        personal_collection = get_or_create_personal_landmark_collection(user=self.user)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                f"private:{view_name}",
                kwargs={"collection_id": personal_collection.id},
            )
        )

        assert response.status_code == status.HTTP_302_FOUND
        assert isinstance(response, HttpResponseRedirect)
        assert response.url == reverse(
            "private:landmark_collection_details",
            kwargs={"collection_id": personal_collection.id},
        )

    def test_write_collection_details_show_color_picker(self) -> None:
        self.collection.permissions.filter(user=self.user).update(
            level=PermissionLevel.READ_AND_WRITE,
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "private:landmark_collection_details",
                kwargs={"collection_id": self.collection.id},
            )
        )

        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        assert 'id="color-picker-btn"' in content
        assert 'name="color"' in content
        assert self.collection.color in content

    def test_details_view_escapes_landmark_table_values(self) -> None:
        LandmarkFactory.create(
            collection=self.collection,
            owner=self.user,
            name="<script>alert(1)</script>",
            latitude="45.1234567",
            longitude="-122.1234567",
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "private:landmark_collection_details",
                kwargs={"collection_id": self.collection.id},
            )
        )

        content = response.content.decode()
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content
        assert "<script>alert(1)</script>" not in content


class GISViewTemplateOGCURLTest(BaseTestCase):
    """ws7g: pin that the GIS-View integration pages render the OGC
    landing-page URL, NOT the raw collections URL.

    Per ``tasks/lessons/ogc-qgis-discovery.md``, user-facing OGC URLs
    must be landing pages so QGIS / ArcGIS Pro can run the standard
    discovery sequence (landing → conformance → collections → items).
    The previous ``user-data`` / ``view-data`` URL names returned a
    collections document directly, breaking the discovery contract.
    """

    def test_gis_views_listing_renders_user_landing_url(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("private:gis_views"))
        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode()
        landing_url = reverse(
            "api:v2:gis-ogc:user-landing",
            kwargs={"key": self.token.key},
        )
        assert landing_url in content, (
            "Personal-GIS-View page must render the user-landing URL"
        )
        # The legacy URL name was removed in ws3a; double-check no
        # template still references the old route name as a string.
        legacy_url_name = "user-data"
        assert legacy_url_name not in content, (
            f"Template still references legacy route name {legacy_url_name!r}"
        )

        # Re-fetch the rendered URL — must NOT 500. This is the exact
        # class of bug that caused the original ArcGIS Pro empty-layer
        # incident: the template generated a URL that the OGC layer
        # then failed to serve. Logging-out before the re-fetch is
        # important: OGC endpoints are deliberately public, the
        # landing page must not depend on session state.
        self.client.logout()
        followed = self.client.get(landing_url)
        assert followed.status_code == status.HTTP_200_OK, (
            f"Rendered OGC URL {landing_url} returned {followed.status_code}, not 200"
        )

    def test_gis_view_integration_renders_view_landing_url(self) -> None:

        gis_view = GISView.objects.create(
            name="Cave Map",
            owner=self.user,
            allow_precise_zoom=False,
        )
        self.client.force_login(self.user)
        # The integration page is registered under
        # ``private:gis_view_gis_integration`` (NOT
        # ``gis_view_details_integration`` — the URL conf names it after
        # the template, not the controller).
        response = self.client.get(
            reverse(
                "private:gis_view_gis_integration",
                kwargs={"gis_view_id": gis_view.id},
            )
        )
        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode()
        landing_url = reverse(
            "api:v2:gis-ogc:view-landing",
            kwargs={"gis_token": gis_view.gis_token},
        )
        assert landing_url in content
        # The legacy ``view-data`` URL name was removed in ws3a; ensure
        # no template still references it as a string token.
        assert "view-data" not in content

        # Re-fetch the rendered URL with no auth — OGC public endpoint.
        self.client.logout()
        followed = self.client.get(landing_url)
        assert followed.status_code == status.HTTP_200_OK, (
            f"Rendered OGC URL {landing_url} returned {followed.status_code}, not 200"
        )

    def test_landmark_collection_integration_url_is_routable(self) -> None:
        """The Landmark Collection GIS integration page renders the OGC
        landing URL — it must be reachable."""

        collection = LandmarkCollectionFactory.create(created_by=self.user.email)
        LandmarkCollectionUserPermissionFactory.create(
            user=self.user,
            collection=collection,
            level=PermissionLevel.READ_ONLY,
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "private:landmark_collection_gis_integration",
                kwargs={"collection_id": collection.id},
            )
        )
        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode()
        landing_url = reverse(
            "api:v2:gis-ogc:landmark-collection-landing",
            kwargs={"gis_token": collection.gis_token},
        )
        assert landing_url in content

        self.client.logout()
        followed = self.client.get(landing_url)
        assert followed.status_code == status.HTTP_200_OK, (
            f"Rendered Landmark OGC URL {landing_url} returned "
            f"{followed.status_code}, not 200"
        )

    def test_landmark_collections_listing_user_landing_is_routable(self) -> None:
        """The All Landmark Collections page renders the OGC user-landing
        URL — it must be reachable for the token owner."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("private:landmark_collections"))
        assert response.status_code == status.HTTP_200_OK

        user_token = Token.objects.get(user=self.user)
        landing_url = reverse(
            "api:v2:gis-ogc:landmark-collections-user-landing",
            kwargs={"key": user_token.key},
        )
        assert landing_url in response.content.decode()

        # Re-fetch and assert the OGC layer serves the URL.
        self.client.logout()
        followed = self.client.get(landing_url)
        assert followed.status_code == status.HTTP_200_OK, (
            f"Rendered user-landing URL {landing_url} returned "
            f"{followed.status_code}, not 200"
        )
