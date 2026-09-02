"""Model coverage for lightweight GIS Layers."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISLayer
from speleodb.gis.models import GISLayerSourceFormat
from speleodb.gis.models import GISLayerUserPermission
from speleodb.gis.models.gis_layer import GIS_LAYER_DESCRIPTION_MAX_LENGTH
from speleodb.users.tests.factories import UserFactory


def _layer(creator_email: str) -> GISLayer:
    return GISLayer.objects.create(
        name="Cave geology",
        created_by=creator_email,
        source_f=SimpleUploadedFile("source.geojson", b"{}"),
        data_f=SimpleUploadedFile("data.geojson", b"{}"),
    )


@pytest.mark.django_db
def test_layer_has_creator_email_and_two_files() -> None:
    creator = UserFactory.create()
    layer = _layer(creator.email)

    assert layer.created_by == creator.email
    assert layer.source_format == GISLayerSourceFormat.GEOJSON
    assert {field.name for field in layer._meta.fields}.issuperset(  # noqa: SLF001
        {"source_f", "data_f", "created_by"}
    )


@pytest.mark.django_db
def test_layer_description_has_a_server_side_limit() -> None:
    creator = UserFactory.create()
    layer = _layer(creator.email)
    layer.description = "x" * (GIS_LAYER_DESCRIPTION_MAX_LENGTH + 1)

    with pytest.raises(ValidationError, match="description"):
        layer.full_clean()


@pytest.mark.django_db
def test_soft_delete_deactivates_permissions_but_keeps_files() -> None:
    creator = UserFactory.create()
    layer = _layer(creator.email)
    permission = GISLayerUserPermission.objects.create(
        user=creator,
        gis_layer=layer,
        level=PermissionLevel.ADMIN,
    )
    source_name = layer.source_f.name
    data_name = layer.data_f.name

    layer.deactivate(creator)

    layer.refresh_from_db()
    permission.refresh_from_db()
    assert not layer.is_active
    assert not permission.is_active
    assert layer.source_f.name == source_name
    assert layer.data_f.name == data_name
