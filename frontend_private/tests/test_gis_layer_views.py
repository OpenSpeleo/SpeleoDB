from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseUserTestCaseMixin
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISLayer
from speleodb.gis.models import GISLayerUserPermission
from speleodb.users.tests.factories import UserFactory

RESPONSIVE_RENDER_COUNT = 2


class GISLayerFrontendViewsTest(BaseUserTestCaseMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.layer = GISLayer.objects.create(
            created_by=self.user.email,
            name="Protected Areas",
            source_f="gis-layers/test/source.kml",
            data_f="gis-layers/test/data.geojson",
        )
        GISLayerUserPermission.objects.create(
            user=self.user,
            gis_layer=self.layer,
            level=PermissionLevel.ADMIN,
        )

    def permission_url(self) -> str:
        return reverse(
            "private:gis_layer_user_permissions",
            kwargs={"layer_id": self.layer.id},
        )

    def details_url(self) -> str:
        return reverse(
            "private:gis_layer_details",
            kwargs={"layer_id": self.layer.id},
        )

    def danger_url(self) -> str:
        return reverse(
            "private:gis_layer_danger_zone",
            kwargs={"layer_id": self.layer.id},
        )

    def test_management_pages_require_authentication(self) -> None:
        assert (
            self.client.get(reverse("private:gis_layers")).status_code
            == status.HTTP_302_FOUND
        )
        for url in (self.details_url(), self.permission_url(), self.danger_url()):
            assert self.client.get(url).status_code == status.HTTP_302_FOUND

    def test_list_declares_private_management_controller(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("private:gis_layers"))

        content = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        assert "My GIS Layers" in content
        assert 'data-speleodb-controller="gis-layers"' in content
        assert reverse("api:v2:gis-layers") in content
        assert 'id="gis-layers-cards-container"' in content
        assert 'class="tracks-table ' in content
        assert 'id="upload-layer-modal"' in content
        assert 'id="edit-layer-modal"' not in content
        assert 'id="delete-layer-modal"' not in content
        assert "right_arrow.svg" in content
        assert "Compatibility notes" not in content
        assert "Landmarks Only" not in content

    def test_details_use_shared_settings_workflow(self) -> None:
        self.client.force_login(self.user)

        content = self.client.get(self.details_url()).content.decode()

        assert "GIS Layer: Protected Areas" in content
        assert "GIS Layer Details" in content
        assert "User Access Control" in content
        assert "Danger Zone" in content
        assert "Download Source" in content
        assert 'id="gis_layer_details_form"' in content
        assert (
            reverse(
                "api:v2:gis-layer-detail",
                kwargs={"id": self.layer.id},
            )
            in content
        )

    def test_reader_gets_read_only_details_and_no_danger_zone(self) -> None:
        reader = UserFactory.create(email="gis-details-reader@example.com")
        GISLayerUserPermission.objects.create(
            user=reader,
            gis_layer=self.layer,
            level=PermissionLevel.READ_ONLY,
        )
        self.client.force_login(reader)

        content = self.client.get(self.details_url()).content.decode()

        assert "Read-only" in content
        assert "Download Source" in content
        assert 'id="btn_submit"' not in content
        assert "Danger Zone" not in content
        response = self.client.get(self.danger_url())
        assert response.status_code == status.HTTP_302_FOUND
        assert response["Location"] == self.details_url()

    def test_admin_can_open_danger_zone(self) -> None:
        self.client.force_login(self.user)

        content = self.client.get(self.danger_url()).content.decode()

        assert "GIS Layer Danger Zone" in content
        assert 'data-speleodb-controller="danger-zone"' in content
        assert (
            reverse(
                "api:v2:gis-layer-detail",
                kwargs={"id": self.layer.id},
            )
            in content
        )

    def test_reader_can_inspect_but_not_mutate_permissions(self) -> None:
        reader = UserFactory.create(email="gis-reader@example.com")
        GISLayerUserPermission.objects.create(
            user=reader,
            gis_layer=self.layer,
            level=PermissionLevel.READ_ONLY,
        )
        self.client.force_login(reader)

        content = self.client.get(self.permission_url()).content.decode()

        assert self.user.email in content
        assert reader.email in content
        assert "Grant Access" not in content
        assert "btn_open_edit_perm" not in content
        assert "btn_delete_perm" not in content
        assert 'data-speleodb-controller="permission-modal"' not in content

    def test_admin_can_manage_other_users_but_not_own_permission(self) -> None:
        collaborator = UserFactory.create(email="gis-writer@example.com")
        GISLayerUserPermission.objects.create(
            user=collaborator,
            gis_layer=self.layer,
            level=PermissionLevel.READ_AND_WRITE,
        )
        self.client.force_login(self.user)

        content = self.client.get(self.permission_url()).content.decode()

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
        assert (
            reverse(
                "api:v2:gis-layer-permissions",
                kwargs={"id": self.layer.id},
            )
            in content
        )
        assert 'value="READ_ONLY"' in content
        assert 'value="READ_AND_WRITE"' in content
        assert 'value="ADMIN"' in content
        assert "WEB_VIEWER" not in content

    def test_inaccessible_inactive_and_revoked_layers_redirect_without_leakage(
        self,
    ) -> None:
        stranger = UserFactory.create(email="gis-stranger@example.com")
        self.client.force_login(stranger)
        response = self.client.get(self.permission_url())
        assert response.status_code == status.HTTP_302_FOUND
        assert response["Location"] == reverse("private:gis_layers")

        permission = GISLayerUserPermission.objects.create(
            user=stranger,
            gis_layer=self.layer,
            level=PermissionLevel.READ_ONLY,
        )
        permission.deactivate(self.user)
        assert (
            self.client.get(self.permission_url()).status_code == status.HTTP_302_FOUND
        )

        self.client.force_login(self.user)
        self.layer.deactivate(self.user)
        assert (
            self.client.get(self.permission_url()).status_code == status.HTTP_302_FOUND
        )

    def test_template_escapes_layer_and_user_names(self) -> None:
        self.layer.name = '<script>alert("layer")</script>'
        self.layer.save(update_fields=["name", "modified_date"])
        self.user.name = '<img src=x onerror="alert(1)">'
        self.user.save(update_fields=["name"])
        self.client.force_login(self.user)

        content = self.client.get(self.permission_url()).content.decode()

        assert "&lt;script&gt;alert" in content
        assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in content
        assert '<script>alert("layer")</script>' not in content
