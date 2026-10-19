"""Real HTTP evidence for every supported OGC family and machine discovery API."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import StreamingHttpResponse
from django.test import Client
from django.test import override_settings
from django.urls import path
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.schema_inventory import current_api_routes
from speleodb.api.v2.tests.factories import ExperimentFactory
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import TokenFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISProjectView
from speleodb.gis.models import GISView
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import ProjectCommit
from speleodb.testing.api_contract import assert_api_response
from speleodb.testing.api_contract import contract_schema
from speleodb.users.tests.factories import UserFactory
from well_known.views import assetlinks
from well_known.views import change_password

if TYPE_CHECKING:
    from speleodb.users.models import User


def _json_response(client: APIClient, path: str, **kwargs: Any) -> tuple[Any, Any]:
    response = client.get(path, **kwargs)
    assert response.status_code == status.HTTP_200_OK
    assert_api_response(response)
    if isinstance(response, StreamingHttpResponse):
        data = json.loads(b"".join(response.streaming_content))
    else:
        data = response.json()
    return response, data


@pytest.mark.django_db
def test_every_ogc_family_and_gis_feed_through_the_supported_mount() -> None:
    """Use real stored GeoJSON and grants; no GitLab repository is necessary."""
    user = cast("User", UserFactory())
    token = TokenFactory.create(user=user)
    project = ProjectFactory.create()
    UserProjectPermissionFactory.create(
        target=user, project=project, level=PermissionLevel.READ_ONLY
    )
    sha = "d" * 40
    commit = ProjectCommit.objects.create(
        id=sha,
        project=project,
        author_name=user.name,
        author_email=user.email,
        authored_date=timezone.now(),
        message="Mounted OGC contract fixture",
    )
    feature_id = "contract-entrance"
    ProjectGeoJSON.objects.create(
        project=project,
        commit=commit,
        file=SimpleUploadedFile(
            "contract.geojson",
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [-87.5, 20.2, -4],
                            },
                            "properties": {"id": feature_id, "name": "Entrance"},
                        }
                    ],
                }
            ).encode(),
            content_type="application/geo+json",
        ),
    )
    view = GISView.objects.create(
        name="Contract view", owner=user, allow_precise_zoom=True
    )
    GISProjectView.objects.create(gis_view=view, project=project, commit_sha=sha)
    collection = LandmarkCollection.objects.create(
        name="Contract landmarks", created_by=user.email
    )
    LandmarkCollectionUserPermission.objects.create(
        collection=collection, user=user, level=PermissionLevel.ADMIN
    )
    landmark = Landmark.objects.create(
        collection=collection,
        name="Contract landmark",
        created_by=user.email,
        latitude=20.2,
        longitude=-87.5,
    )
    experiment = ExperimentFactory.create(created_by=user.email)
    client = APIClient()
    base = "/api/v2/gis-ogc"
    families = [
        (f"{base}/view/{view.gis_token}", f"{sha}_points", feature_id),
        (f"{base}/user/{token.key}", f"{sha}_points", feature_id),
        (
            f"{base}/landmark-collection/{collection.gis_token}",
            "landmarks",
            str(landmark.id),
        ),
        (
            f"{base}/landmark-collections/user/{token.key}",
            str(collection.id),
            str(landmark.id),
        ),
    ]
    for family, collection_id, item_id in families:
        _, landing = _json_response(client, family)
        assert landing["title"]
        assert all(
            link["href"].startswith("http://testserver/") for link in landing["links"]
        )
        _, formatted_landing = _json_response(client, family, data={"format": "json"})
        assert formatted_landing["title"] == landing["title"]
        _, conformance = _json_response(client, family + "/conformance")
        assert conformance["conformsTo"]
        _, collections = _json_response(client, family + "/collections")
        assert collection_id in {entry["id"] for entry in collections["collections"]}
        collection_url = f"{family}/collections/{collection_id}"
        _, metadata = _json_response(client, collection_url)
        assert metadata["itemType"] == "feature"
        items_url = collection_url + "/items"
        response, items = _json_response(client, items_url)
        assert items["numberReturned"] == 1
        assert str(items["features"][0]["id"]) == item_id
        assert "ETag" in response
        assert "Cache-Control" in response
        assert "Content-Disposition" in response
        unchanged = client.get(items_url, headers={"If-None-Match": response["ETag"]})
        assert unchanged.status_code == status.HTTP_304_NOT_MODIFIED
        assert_api_response(unchanged)
        _, feature = _json_response(client, f"{items_url}/{item_id}")
        assert str(feature["id"]) == item_id
        assert feature["links"]
        _, filtered = _json_response(
            client,
            items_url,
            data={
                "bbox": "-88,20,-87,21",
                "limit": 1,
                "offset": 0,
            },
        )
        assert filtered["numberMatched"] == 1
        _, empty_query = _json_response(
            client,
            items_url,
            data={
                "bbox": "",
                "datetime": "",
                "limit": "",
                "offset": "",
            },
        )
        assert empty_query["features"] == items["features"]
        assert empty_query["numberMatched"] == items["numberMatched"]
        assert empty_query["numberReturned"] == items["numberReturned"]
        for query in ({"bbox": "-88,20,0,-87,21"}, {"offset": 10**9 + 1}):
            invalid = client.get(items_url, data=query)
            assert invalid.status_code == status.HTTP_400_BAD_REQUEST
            assert_api_response(invalid)
        if "/landmark" not in family:
            for suffix in ("", "/items", f"/items/{item_id}"):
                gone = client.get(f"{family}/collections/{sha}{suffix}")
                assert gone.status_code == status.HTTP_410_GONE
                assert_api_response(gone)
                assert gone.json()["status"] == status.HTTP_410_GONE
                assert "Link" in gone
    _, document = _json_response(client, base + "/openapi/")
    assert document["openapi"] == "3.0.3"
    _, feed = _json_response(client, f"{base}/experiment/{experiment.gis_token}")
    assert feed == {"type": "FeatureCollection", "features": []}
    _, public = _json_response(client, f"{base}/view/{view.gis_token}/geojson")
    assert public["view_name"] == view.name
    _, private = _json_response(
        client,
        f"/api/v2/gis_view/{view.id}/",
        data={"expires_in": 1},
        headers={"Authorization": f"Token {token.key}"},
    )
    assert private["view_name"] == view.name


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/.well-known/assetlinks.json",
        "/.well-known/apple-app-site-association",
        "/.well-known/passkey-endpoints",
        "/api/schema/?format=json",
    ],
)
def test_discovery_documents_have_real_contract_evidence(
    client: Client, path: str
) -> None:
    response = client.get(path)
    assert response.status_code == status.HTTP_200_OK
    assert_api_response(response)
    if path.startswith("/api/schema/"):
        document = response.json()
        assert set(document["paths"]) == set(contract_schema()["paths"])


class _UnusualAPIMount:
    urlpatterns = [path("outside-known-api-prefixes/", assetlinks)]


class _UnadaptedFunctionMount:
    urlpatterns = [path("api/new-handler/", change_password)]


def test_inventory_discovers_api_views_outside_known_mounts() -> None:
    with override_settings(ROOT_URLCONF=_UnusualAPIMount):
        routes = current_api_routes()
    assert {(route["path"], route["method"]) for route in routes} == {
        ("/outside-known-api-prefixes/", "get")
    }


def test_inventory_rejects_unadapted_handlers_inside_api_mounts() -> None:
    with (
        override_settings(ROOT_URLCONF=_UnadaptedFunctionMount),
        pytest.raises(
            ValueError, match="API mount needs an explicit inventory adapter"
        ),
    ):
        current_api_routes()
