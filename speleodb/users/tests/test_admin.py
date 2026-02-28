# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from importlib import reload
from typing import TYPE_CHECKING

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.exceptions import AlreadyRegistered
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from pytest_django.asserts import assertRedirects
from rest_framework import status

from speleodb.common.enums import UserAction
from speleodb.common.enums import UserApplication
from speleodb.gis.models import ExplorationLead
from speleodb.gis.models import GISView
from speleodb.gis.models import Landmark
from speleodb.users.backends import StaffFullAdminAccessBackend
from speleodb.users.models import AccountEvent
from speleodb.users.models import SurveyTeam
from speleodb.users.models import User
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test.client import Client
    from django.test.client import RequestFactory
    from pytest_django.fixtures import SettingsWrapper

    from speleodb.surveys.models import Project


class TestUserAdmin:
    def test_changelist(self, admin_client: Client) -> None:
        url = reverse("admin:users_user_changelist")
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore[attr-defined]

    def test_search(self, admin_client: Client) -> None:
        url = reverse("admin:users_user_changelist")
        response = admin_client.get(url, data={"q": "test"})
        assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore[attr-defined]

    def test_add(self, admin_client: Client) -> None:
        url = reverse("admin:users_user_add")
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore[attr-defined]

        response = admin_client.post(
            url,
            data={
                "email": "new-admin@example.com",
                "password1": "My_R@ndom-P@ssw0rd",
                "password2": "My_R@ndom-P@ssw0rd",
            },
        )
        assert response.status_code == status.HTTP_302_FOUND, response.data  # type: ignore[attr-defined]
        assert User.objects.filter(email="new-admin@example.com").exists()

    def test_view_user(self, admin_client: Client) -> None:
        user = User.objects.get(email="admin@example.com")
        url = reverse("admin:users_user_change", kwargs={"object_id": user.pk})
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore[attr-defined]

    @pytest.fixture
    def _force_allauth(self, settings: SettingsWrapper) -> None:
        settings.DJANGO_ADMIN_FORCE_ALLAUTH = True
        # Reload the admin module to apply the setting change
        import speleodb.users.admin as users_admin  # noqa: PLC0415

        with contextlib.suppress(AlreadyRegistered):
            reload(users_admin)

    @pytest.mark.django_db
    @pytest.mark.usefixtures("_force_allauth")
    def test_allauth_login(self, rf: RequestFactory, settings: SettingsWrapper) -> None:
        request = rf.get("/fake-url")
        request.user = AnonymousUser()
        response = admin.site.login(request)

        # The `admin` login view should redirect to the `allauth` login view
        target_url = reverse(settings.LOGIN_URL) + "?next=" + request.path
        assertRedirects(response, target_url, fetch_redirect_response=False)


@pytest.mark.django_db
class TestAccountEventAdmin:
    @pytest.fixture
    def account_event(self, user: User) -> AccountEvent:
        return AccountEvent.objects.create(
            user=user,
            ip_addr="198.51.100.21",
            user_agent="Mozilla/5.0",
            action=UserAction.LOGIN,
            application=UserApplication.WEBSITE,
        )

    def test_changelist(self, admin_client: Client) -> None:
        url = reverse("admin:users_accountevent_changelist")
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore[attr-defined]

    def test_add_is_blocked(self, admin_client: Client) -> None:
        url = reverse("admin:users_accountevent_add")
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data  # type: ignore[attr-defined]

    def test_change_view_is_readonly(
        self, admin_client: Client, account_event: AccountEvent
    ) -> None:
        change_url = reverse(
            "admin:users_accountevent_change",
            kwargs={"object_id": account_event.pk},
        )
        response = admin_client.get(change_url)
        assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore[attr-defined]

        response = admin_client.post(
            change_url,
            data={
                "user": account_event.user_id,
                "ip_addr": "198.51.100.99",
                "user_agent": "tampered-agent",
                "action": UserAction.LOGOUT,
                "application": UserApplication.ANDROID_APP,
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data  # type: ignore[attr-defined]

        account_event.refresh_from_db()
        assert account_event.action == UserAction.LOGIN
        assert account_event.ip_addr == "198.51.100.21"

    def test_delete_is_allowed(
        self, admin_client: Client, account_event: AccountEvent
    ) -> None:
        delete_url = reverse(
            "admin:users_accountevent_delete",
            kwargs={"object_id": account_event.pk},
        )
        response = admin_client.post(delete_url, data={"post": "yes"})
        assert response.status_code == status.HTTP_302_FOUND, response.data  # type: ignore[attr-defined]
        assert not AccountEvent.objects.filter(pk=account_event.pk).exists()


# ---------------------------------------------------------------------------
# StaffFullAdminAccessBackend -- unit tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStaffFullAdminAccessBackend:
    """Direct tests for the backend methods, independent of Django internals."""

    def test_has_perm_active_staff(self, staff_user: User) -> None:
        backend = StaffFullAdminAccessBackend()
        assert backend.has_perm(staff_user, "surveys.view_project")

    def test_has_perm_regular_user(self, user: User) -> None:
        backend = StaffFullAdminAccessBackend()
        assert not backend.has_perm(user, "surveys.view_project")

    def test_has_perm_inactive_staff(self, db: None) -> None:
        inactive = UserFactory.create(
            is_staff=True, is_superuser=False, is_active=False
        )
        backend = StaffFullAdminAccessBackend()
        assert not backend.has_perm(inactive, "surveys.view_project")

    def test_has_module_perms_active_staff(self, staff_user: User) -> None:
        backend = StaffFullAdminAccessBackend()
        assert backend.has_module_perms(staff_user, "surveys")

    def test_has_module_perms_regular_user(self, user: User) -> None:
        backend = StaffFullAdminAccessBackend()
        assert not backend.has_module_perms(user, "surveys")

    def test_authenticate_returns_none(self, staff_user: User) -> None:
        backend = StaffFullAdminAccessBackend()
        assert backend.authenticate(request=None) is None  # type: ignore[func-returns-value]

    @pytest.mark.parametrize("app_label", ["auth", "sites", "django_celery_beat"])
    def test_blocked_apps_denied_for_staff(
        self, staff_user: User, app_label: str
    ) -> None:
        backend = StaffFullAdminAccessBackend()
        assert not backend.has_module_perms(staff_user, app_label)
        assert not backend.has_perm(staff_user, f"{app_label}.view_anything")

    def test_delete_perm_denied_for_staff(self, staff_user: User) -> None:
        backend = StaffFullAdminAccessBackend()
        assert not backend.has_perm(staff_user, "surveys.delete_project")
        assert not backend.has_perm(staff_user, "gis.delete_station")

    def test_non_delete_perms_allowed_for_staff(self, staff_user: User) -> None:
        backend = StaffFullAdminAccessBackend()
        assert backend.has_perm(staff_user, "surveys.view_project")
        assert backend.has_perm(staff_user, "surveys.add_project")
        assert backend.has_perm(staff_user, "surveys.change_project")


# ---------------------------------------------------------------------------
# Permission chain -- integration through Django's User.has_perm / has_module_perms
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStaffPermissionChain:
    """Verify the backend participates in Django's full auth-backend chain."""

    def test_staff_has_perm_via_chain(self, staff_user: User) -> None:
        assert staff_user.has_perm("surveys.view_project")

    def test_staff_has_module_perms_via_chain(self, staff_user: User) -> None:
        assert staff_user.has_module_perms("surveys")

    def test_regular_user_lacks_perm(self, user: User) -> None:
        assert not user.has_perm("surveys.view_project")

    def test_regular_user_lacks_module_perms(self, user: User) -> None:
        assert not user.has_module_perms("surveys")

    def test_staff_has_perms_for_multiple_apps(self, staff_user: User) -> None:
        for app_label in ("surveys", "gis", "plugins", "users"):
            assert staff_user.has_module_perms(app_label), (
                f"staff_user.has_module_perms('{app_label}') returned False"
            )

    def test_staff_delete_denied_via_chain(self, staff_user: User) -> None:
        assert not staff_user.has_perm("surveys.delete_project")
        assert not staff_user.has_perm("gis.delete_station")


# ---------------------------------------------------------------------------
# Admin access -- staff sees all apps, can't modify users
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStaffAdminAccess:
    """Integration tests hitting the admin views as a staff (non-superuser)."""

    def test_admin_index_accessible(self, staff_client: Client) -> None:
        response = staff_client.get(reverse("admin:index"))
        assert response.status_code == status.HTTP_200_OK

    def test_admin_index_shows_multiple_apps(self, staff_client: Client) -> None:
        response = staff_client.get(reverse("admin:index"))
        body = response.content.decode()
        for app_label in ("surveys", "gis", "plugins"):
            assert app_label in body, (
                f"App '{app_label}' not found in admin index for staff user"
            )

    # -- User model: view-only for staff -----------------------------------

    def test_staff_can_view_user_changelist(self, staff_client: Client) -> None:
        url = reverse("admin:users_user_changelist")
        response = staff_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_staff_can_view_user_detail(
        self, staff_client: Client, staff_user: User
    ) -> None:
        url = reverse("admin:users_user_change", kwargs={"object_id": staff_user.pk})
        response = staff_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_staff_cannot_add_user(self, staff_client: Client) -> None:
        url = reverse("admin:users_user_add")
        response = staff_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff_cannot_change_user(
        self, staff_client: Client, staff_user: User
    ) -> None:
        url = reverse("admin:users_user_change", kwargs={"object_id": staff_user.pk})
        response = staff_client.post(url, data={"name": "Tampered"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff_cannot_delete_user(
        self, staff_client: Client, staff_user: User
    ) -> None:
        url = reverse("admin:users_user_delete", kwargs={"object_id": staff_user.pk})
        response = staff_client.post(url, data={"post": "yes"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # -- Other models: view/add/change but no delete for staff ----------------

    def test_staff_can_access_surveys(self, staff_client: Client) -> None:
        url = reverse("admin:surveys_project_changelist")
        response = staff_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_staff_cannot_see_project_coordinates(
        self, staff_client: Client, project: Project
    ) -> None:
        url = reverse("admin:surveys_project_changelist")
        response = staff_client.get(url)
        body = response.content.decode()
        assert "column-latitude" not in body
        assert "column-longitude" not in body

    def test_superuser_can_see_project_coordinates(
        self, admin_client: Client, project: Project
    ) -> None:
        url = reverse("admin:surveys_project_changelist")
        response = admin_client.get(url)
        body = response.content.decode()
        assert "column-latitude" in body
        assert "column-longitude" in body

    # -- Landmark: lat/lon hidden from staff (list + detail) ----------------

    @pytest.fixture
    def landmark(self, staff_user: User) -> Landmark:
        return Landmark.objects.create(
            name="Test Cave", latitude=46.0, longitude=7.0, user=staff_user
        )

    def test_staff_landmark_list_hides_coordinates(
        self, staff_client: Client, landmark: Landmark
    ) -> None:
        url = reverse("admin:gis_landmark_changelist")
        response = staff_client.get(url)
        body = response.content.decode()
        assert "column-latitude" not in body
        assert "column-longitude" not in body

    def test_superuser_landmark_list_shows_coordinates(
        self, admin_client: Client, landmark: Landmark
    ) -> None:
        url = reverse("admin:gis_landmark_changelist")
        response = admin_client.get(url)
        body = response.content.decode()
        assert "column-latitude" in body
        assert "column-longitude" in body

    def test_staff_landmark_detail_hides_location_section(
        self, staff_client: Client, landmark: Landmark
    ) -> None:
        url = reverse("admin:gis_landmark_change", kwargs={"object_id": landmark.pk})
        response = staff_client.get(url)
        body = response.content.decode()
        assert "Location" not in body
        assert "latitude" not in body.lower()
        assert "longitude" not in body.lower()

    def test_superuser_landmark_detail_shows_coordinates(
        self, admin_client: Client, landmark: Landmark
    ) -> None:
        url = reverse("admin:gis_landmark_change", kwargs={"object_id": landmark.pk})
        response = admin_client.get(url)
        body = response.content.decode()
        assert "latitude" in body.lower()
        assert "longitude" in body.lower()

    # -- ExplorationLead: coordinates section hidden from staff --------------

    @pytest.fixture
    def explo_lead(self, staff_user: User, project: Project) -> ExplorationLead:
        return ExplorationLead.objects.create(
            project=project,
            latitude=46.0,
            longitude=7.0,
            created_by=staff_user.email,
        )

    def test_staff_explo_lead_list_hides_coordinates(
        self, staff_client: Client, explo_lead: ExplorationLead
    ) -> None:
        url = reverse("admin:gis_explorationlead_changelist")
        response = staff_client.get(url)
        body = response.content.decode()
        assert "column-latitude" not in body
        assert "column-longitude" not in body

    def test_superuser_explo_lead_list_shows_coordinates(
        self, admin_client: Client, explo_lead: ExplorationLead
    ) -> None:
        url = reverse("admin:gis_explorationlead_changelist")
        response = admin_client.get(url)
        body = response.content.decode()
        assert "column-latitude" in body
        assert "column-longitude" in body

    def test_staff_explo_lead_detail_hides_coordinates_section(
        self, staff_client: Client, explo_lead: ExplorationLead
    ) -> None:
        url = reverse(
            "admin:gis_explorationlead_change",
            kwargs={"object_id": explo_lead.pk},
        )
        response = staff_client.get(url)
        body = response.content.decode()
        assert "Coordinates" not in body
        assert "latitude" not in body.lower()
        assert "longitude" not in body.lower()

    def test_superuser_explo_lead_detail_shows_coordinates_section(
        self, admin_client: Client, explo_lead: ExplorationLead
    ) -> None:
        url = reverse(
            "admin:gis_explorationlead_change",
            kwargs={"object_id": explo_lead.pk},
        )
        response = admin_client.get(url)
        body = response.content.decode()
        assert "Coordinates" in body
        assert "latitude" in body.lower()
        assert "longitude" in body.lower()

    # -- GISView: token/api_url hidden from staff ----------------------------

    @pytest.fixture
    def gis_view(self, staff_user: User) -> GISView:
        return GISView.objects.create(
            name="Test View", owner=staff_user, allow_precise_zoom=False
        )

    def test_staff_gis_view_list_hides_token(
        self, staff_client: Client, gis_view: GISView
    ) -> None:
        url = reverse("admin:gis_gisview_changelist")
        response = staff_client.get(url)
        body = response.content.decode()
        assert "column-token_preview" not in body

    def test_superuser_gis_view_list_shows_token(
        self, admin_client: Client, gis_view: GISView
    ) -> None:
        url = reverse("admin:gis_gisview_changelist")
        response = admin_client.get(url)
        body = response.content.decode()
        assert "column-token_preview" in body

    def test_staff_gis_view_detail_hides_sensitive_fields(
        self, staff_client: Client, gis_view: GISView
    ) -> None:
        url = reverse("admin:gis_gisview_change", kwargs={"object_id": gis_view.pk})
        response = staff_client.get(url)
        body = response.content.decode()
        assert "gis_token" not in body
        assert "api_url_display" not in body

    def test_superuser_gis_view_detail_shows_sensitive_fields(
        self, admin_client: Client, gis_view: GISView
    ) -> None:
        url = reverse("admin:gis_gisview_change", kwargs={"object_id": gis_view.pk})
        response = admin_client.get(url)
        body = response.content.decode()
        assert "gis_token" in body

    def test_staff_can_access_plugins(self, staff_client: Client) -> None:
        url = reverse("admin:plugins_publicannoucement_changelist")
        response = staff_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_staff_cannot_delete_survey_team(
        self, staff_client: Client, staff_user: User
    ) -> None:
        team = SurveyTeam.objects.create(name="TestTeam", country="US")
        url = reverse("admin:users_surveyteam_delete", kwargs={"object_id": team.pk})
        response = staff_client.post(url, data={"post": "yes"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert SurveyTeam.objects.filter(pk=team.pk).exists()

    # -- EmailAddress: view-only for staff ----------------------------------

    def test_staff_can_view_email_changelist(self, staff_client: Client) -> None:
        url = reverse("admin:account_emailaddress_changelist")
        response = staff_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_staff_cannot_add_email(self, staff_client: Client) -> None:
        url = reverse("admin:account_emailaddress_add")
        response = staff_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff_cannot_delete_email(
        self, staff_client: Client, staff_user: User
    ) -> None:

        ea = EmailAddress.objects.create(
            user=staff_user, email=staff_user.email, verified=True, primary=True
        )
        url = reverse("admin:account_emailaddress_delete", kwargs={"object_id": ea.pk})
        response = staff_client.post(url, data={"post": "yes"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # -- Tokens: completely hidden from staff --------------------------------

    def test_staff_cannot_see_tokens(self, staff_client: Client) -> None:
        response = staff_client.get(reverse("admin:index"))
        body = response.content.decode()
        assert "token" not in body.lower() or "authtoken" not in body.lower()

    def test_staff_cannot_access_token_changelist(self, staff_client: Client) -> None:
        url = reverse("admin:authtoken_tokenproxy_changelist")
        response = staff_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_superuser_can_access_tokens(self, admin_client: Client) -> None:
        url = reverse("admin:authtoken_tokenproxy_changelist")
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    # -- Blocked apps: completely hidden from staff --------------------------

    def test_staff_cannot_access_sites(self, staff_client: Client) -> None:
        url = reverse("admin:sites_site_changelist")
        response = staff_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff_cannot_access_auth_group(self, staff_client: Client) -> None:
        url = reverse("admin:auth_group_changelist")
        response = staff_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff_cannot_access_periodic_tasks(self, staff_client: Client) -> None:
        url = reverse("admin:django_celery_beat_periodictask_changelist")
        response = staff_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_index_hides_blocked_apps(self, staff_client: Client) -> None:
        response = staff_client.get(reverse("admin:index"))
        body = response.content.decode()
        assert "Periodic tasks" not in body
        assert "Sites" not in body
        assert "Authentication and Authorization" not in body


# ---------------------------------------------------------------------------
# Hijack column -- hidden for staff
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStaffHijackRestriction:
    @pytest.mark.skipif(
        "hijack" not in settings.INSTALLED_APPS,
        reason="django-hijack not installed",
    )
    def test_staff_user_changelist_has_no_hijack_column(
        self, staff_client: Client
    ) -> None:
        url = reverse("admin:users_user_changelist")
        response = staff_client.get(url)
        body = response.content.decode()
        assert "impersonate user" not in body.lower()

    @pytest.mark.skipif(
        "hijack" not in settings.INSTALLED_APPS,
        reason="django-hijack not installed",
    )
    def test_superuser_changelist_has_hijack_column(self, admin_client: Client) -> None:
        url = reverse("admin:users_user_changelist")
        response = admin_client.get(url)
        body = response.content.decode()
        assert "impersonate user" in body.lower()
