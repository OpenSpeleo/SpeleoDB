"""Tests for Landmark Collection OGC endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol
from typing import cast

import orjson
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from speleodb.common.enums import PermissionLevel
from speleodb.gis.landmark_collections import get_or_create_personal_landmark_collection
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission
from speleodb.users.models import User

if TYPE_CHECKING:
    from collections.abc import Iterable


class _StreamingResponse(Protocol):
    streaming_content: Iterable[bytes]


def _streaming_json(response: object) -> dict[str, Any]:
    streaming_response = cast("_StreamingResponse", response)
    content = b"".join(streaming_response.streaming_content)
    return cast("dict[str, Any]", orjson.loads(content))


@pytest.mark.django_db
class TestLandmarkCollectionOGC:
    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def owner(self) -> User:
        return User.objects.create_user(email="owner@example.com")

    @pytest.fixture
    def collection(self, owner: User) -> LandmarkCollection:
        collection = LandmarkCollection.objects.create(
            name="Benchmarks",
            description="Shared points",
            created_by=owner.email,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=owner,
            level=PermissionLevel.ADMIN,
        )
        return collection

    @pytest.fixture
    def user_token(self, owner: User) -> Token:
        return Token.objects.create(
            user=owner,
            key="a1b2c3d4e5f6a7b8c9d0" * 2,
        )

    def test_landing_conformance_and_collection_metadata(
        self, api_client: APIClient, collection: LandmarkCollection
    ) -> None:
        landing = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collection-landing",
                kwargs={"gis_token": collection.gis_token},
            )
        )
        assert landing.status_code == status.HTTP_200_OK
        assert landing.json()["title"] == "SpeleoDB Landmark Collection"
        data_link = next(
            link for link in landing.json()["links"] if link["rel"] == "data"
        )
        assert data_link["href"].endswith(
            reverse(
                "api:v2:gis-ogc:landmark-collection-collections",
                kwargs={"gis_token": collection.gis_token},
            )
        )

        conformance = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collection-conformance",
                kwargs={"gis_token": collection.gis_token},
            )
        )
        assert conformance.status_code == status.HTTP_200_OK
        assert "conformsTo" in conformance.json()

        collections = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collection-collections",
                kwargs={"gis_token": collection.gis_token},
            )
        )
        assert collections.status_code == status.HTTP_200_OK
        collection_meta = collections.json()["collections"][0]
        assert collection_meta["id"] == "landmarks"
        items_link = next(
            link for link in collection_meta["links"] if link["rel"] == "items"
        )
        assert items_link["href"].endswith(
            reverse(
                "api:v2:gis-ogc:landmark-collection-collection-items",
                kwargs={
                    "gis_token": collection.gis_token,
                    "collection_id": "landmarks",
                },
            )
        )

        metadata = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collection-collection",
                kwargs={
                    "gis_token": collection.gis_token,
                    "collection_id": "landmarks",
                },
            )
        )
        assert metadata.status_code == status.HTTP_200_OK
        assert metadata.json()["id"] == "landmarks"

    def test_collections_query_params_do_not_corrupt_child_links(
        self,
        api_client: APIClient,
        collection: LandmarkCollection,
    ) -> None:
        collections_url = reverse(
            "api:v2:gis-ogc:landmark-collection-collections",
            kwargs={"gis_token": collection.gis_token},
        )
        response = api_client.get(f"{collections_url}?f=json")

        assert response.status_code == status.HTTP_200_OK
        layer = response.json()["collections"][0]
        metadata_link = next(link for link in layer["links"] if link["rel"] == "self")
        items_link = next(link for link in layer["links"] if link["rel"] == "items")
        expected_metadata_path = reverse(
            "api:v2:gis-ogc:landmark-collection-collection",
            kwargs={
                "gis_token": collection.gis_token,
                "collection_id": "landmarks",
            },
        )
        expected_items_path = reverse(
            "api:v2:gis-ogc:landmark-collection-collection-items",
            kwargs={
                "gis_token": collection.gis_token,
                "collection_id": "landmarks",
            },
        )

        assert metadata_link["href"].endswith(expected_metadata_path)
        assert items_link["href"].endswith(expected_items_path)
        assert "?f=json/landmarks" not in metadata_link["href"]
        assert "?f=json/landmarks" not in items_link["href"]

    def test_items_returns_point_geojson_and_etag(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
    ) -> None:
        Landmark.objects.create(
            name="Entrance",
            description="Main",
            latitude=45.1234567,
            longitude=-122.1234567,
            created_by=owner.email,
            collection=collection,
        )

        url = reverse(
            "api:v2:gis-ogc:landmark-collection-collection-items",
            kwargs={"gis_token": collection.gis_token, "collection_id": "landmarks"},
        )
        response = api_client.get(url, HTTP_ACCEPT="application/geo+json")

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/geo+json"
        assert response["Cache-Control"] == "public, max-age=60, must-revalidate"
        assert response["ETag"]

        payload = _streaming_json(response)
        assert payload["type"] == "FeatureCollection"
        feature = payload["features"][0]
        assert feature["geometry"]["type"] == "Point"
        assert feature["properties"]["name"] == "Entrance"

        cached = api_client.get(url, HTTP_IF_NONE_MATCH=response["ETag"])
        assert cached.status_code == status.HTTP_304_NOT_MODIFIED
        assert cached["ETag"] == response["ETag"]

    def test_personal_collection_token_returns_point_geojson(
        self,
        api_client: APIClient,
        owner: User,
    ) -> None:
        personal_collection = get_or_create_personal_landmark_collection(user=owner)
        Landmark.objects.create(
            name="Private Entrance",
            description="Owner point",
            latitude=46.1234567,
            longitude=-123.1234567,
            created_by=owner.email,
            collection=personal_collection,
        )

        url = reverse(
            "api:v2:gis-ogc:landmark-collection-collection-items",
            kwargs={
                "gis_token": personal_collection.gis_token,
                "collection_id": "landmarks",
            },
        )
        response = api_client.get(url, HTTP_ACCEPT="application/geo+json")

        assert response.status_code == status.HTTP_200_OK
        payload = _streaming_json(response)
        assert payload["type"] == "FeatureCollection"
        feature = payload["features"][0]
        assert feature["geometry"]["type"] == "Point"
        assert feature["properties"]["name"] == "Private Entrance"

    def test_invalid_or_inactive_collection_token_404(
        self, api_client: APIClient, collection: LandmarkCollection
    ) -> None:
        invalid = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collection-collections",
                kwargs={"gis_token": "a" * 40},
            )
        )
        assert invalid.status_code == status.HTTP_404_NOT_FOUND

        collection.is_active = False
        collection.save()
        inactive = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collection-collections",
                kwargs={"gis_token": collection.gis_token},
            )
        )
        assert inactive.status_code == status.HTTP_404_NOT_FOUND

    def test_legacy_bare_collection_paths_are_404(
        self,
        api_client: APIClient,
        collection: LandmarkCollection,
    ) -> None:
        """ws3a/ws7f: bare-token aliases were removed; old URLs must 404.

        The previous ``landmark-collection-data``,
        ``landmark-collection-layer``, and
        ``landmark-collection-layer-items`` aliases violated the OGC
        discovery convention by exposing collection documents at
        non-canonical paths. After ws3a they are gone — clients that
        cached those URLs must re-fetch the landing page.
        """
        token = collection.gis_token
        # Direct URL strings (not reverse() — those names are gone).
        # The slash-free landing URL ``/landmark-collection/<token>``
        # is now the canonical OGC discovery entry point and returns
        # 200 directly. The trailing-slash variant
        # ``/landmark-collection/<token>/`` returns 404 (Django's
        # APPEND_SLASH only adds slashes, it does not remove them) —
        # see ``test_landing_url_with_trailing_slash_returns_404`` in
        # ``test_ogc_compliance.py``. The bare-sha
        # collection / items routes from the previous API surface
        # also 404.
        bare_landing = api_client.get(
            f"/api/v2/gis-ogc/landmark-collection/{token}",
        )
        trailing_slash_landing = api_client.get(
            f"/api/v2/gis-ogc/landmark-collection/{token}/",
        )
        bare_layer = api_client.get(
            f"/api/v2/gis-ogc/landmark-collection/{token}/landmarks",
        )
        bare_layer_items = api_client.get(
            f"/api/v2/gis-ogc/landmark-collection/{token}/landmarks/items",
        )
        assert bare_landing.status_code == status.HTTP_200_OK
        assert trailing_slash_landing.status_code == status.HTTP_404_NOT_FOUND
        # ``/landmarks`` and ``/landmarks/items`` were never canonical
        # under the new API surface (those routes live under
        # ``/collections/landmarks``); they 404 outright.
        assert bare_layer.status_code == status.HTTP_404_NOT_FOUND
        assert bare_layer_items.status_code == status.HTTP_404_NOT_FOUND

    def test_user_token_landing_conformance_and_collections(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
        user_token: Token,
    ) -> None:
        personal_collection = get_or_create_personal_landmark_collection(user=owner)
        read_collection = LandmarkCollection.objects.create(
            name="Read Collection",
            created_by=owner.email,
        )
        write_collection = LandmarkCollection.objects.create(
            name="Write Collection",
            created_by=owner.email,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=read_collection,
            user=owner,
            level=PermissionLevel.READ_ONLY,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=write_collection,
            user=owner,
            level=PermissionLevel.READ_AND_WRITE,
        )

        landing = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collections-user-landing",
                kwargs={"key": user_token.key},
            )
        )
        assert landing.status_code == status.HTTP_200_OK
        assert landing.json()["title"] == "SpeleoDB Landmark Collections"
        data_link = next(
            link for link in landing.json()["links"] if link["rel"] == "data"
        )
        assert data_link["href"].endswith(
            reverse(
                "api:v2:gis-ogc:landmark-collections-user-collections",
                kwargs={"key": user_token.key},
            )
        )

        conformance = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collections-user-conformance",
                kwargs={"key": user_token.key},
            )
        )
        assert conformance.status_code == status.HTTP_200_OK
        assert "conformsTo" in conformance.json()

        collections = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collections-user-collections",
                kwargs={"key": user_token.key},
            )
        )
        assert collections.status_code == status.HTTP_200_OK
        collection_ids = {item["id"] for item in collections.json()["collections"]}
        assert collection_ids == {
            str(personal_collection.id),
            str(collection.id),
            str(read_collection.id),
            str(write_collection.id),
        }

    def test_user_token_collections_filter_inactive_and_inaccessible(
        self,
        api_client: APIClient,
        owner: User,
        user_token: Token,
    ) -> None:
        accessible_collection = LandmarkCollection.objects.create(
            name="Accessible",
            created_by=owner.email,
        )
        inactive_collection = LandmarkCollection.objects.create(
            name="Inactive",
            created_by=owner.email,
            is_active=False,
        )
        inactive_permission_collection = LandmarkCollection.objects.create(
            name="Inactive Permission",
            created_by=owner.email,
        )
        inaccessible_collection = LandmarkCollection.objects.create(
            name="No Permission",
            created_by=owner.email,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=accessible_collection,
            user=owner,
            level=PermissionLevel.READ_ONLY,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=inactive_collection,
            user=owner,
            level=PermissionLevel.ADMIN,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=inactive_permission_collection,
            user=owner,
            level=PermissionLevel.READ_ONLY,
            is_active=False,
        )

        response = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collections-user-collections",
                kwargs={"key": user_token.key},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        collection_ids = {item["id"] for item in response.json()["collections"]}
        assert str(accessible_collection.id) in collection_ids
        assert str(inactive_collection.id) not in collection_ids
        assert str(inactive_permission_collection.id) not in collection_ids
        assert str(inaccessible_collection.id) not in collection_ids

    def test_user_token_metadata_and_items_are_collection_scoped(
        self,
        api_client: APIClient,
        owner: User,
        user_token: Token,
    ) -> None:
        first_collection = LandmarkCollection.objects.create(
            name="First",
            created_by=owner.email,
        )
        second_collection = LandmarkCollection.objects.create(
            name="Second",
            created_by=owner.email,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=first_collection,
            user=owner,
            level=PermissionLevel.READ_ONLY,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=second_collection,
            user=owner,
            level=PermissionLevel.READ_ONLY,
        )
        Landmark.objects.create(
            name="First Point",
            latitude=45.0,
            longitude=-122.0,
            created_by=owner.email,
            collection=first_collection,
        )
        Landmark.objects.create(
            name="Second Point",
            latitude=46.0,
            longitude=-123.0,
            created_by=owner.email,
            collection=second_collection,
        )

        metadata = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collections-user-collection",
                kwargs={"key": user_token.key, "collection_id": first_collection.id},
            )
        )
        assert metadata.status_code == status.HTTP_200_OK
        assert metadata.json()["id"] == str(first_collection.id)
        assert metadata.json()["title"] == "First"

        items_url = reverse(
            "api:v2:gis-ogc:landmark-collections-user-collection-items",
            kwargs={"key": user_token.key, "collection_id": first_collection.id},
        )
        items = api_client.get(items_url, HTTP_ACCEPT="application/geo+json")
        assert items.status_code == status.HTTP_200_OK
        assert items["Content-Type"] == "application/geo+json"
        assert items["Cache-Control"] == "public, max-age=60, must-revalidate"
        assert items["ETag"]

        payload = _streaming_json(items)
        feature_names = {
            feature["properties"]["name"] for feature in payload["features"]
        }
        assert feature_names == {"First Point"}
        feature = payload["features"][0]
        assert feature["geometry"]["type"] == "Point"

        cached = api_client.get(items_url, HTTP_IF_NONE_MATCH=items["ETag"])
        assert cached.status_code == status.HTTP_304_NOT_MODIFIED
        assert cached["ETag"] == items["ETag"]

    @pytest.mark.parametrize(
        "accept_header",
        ["application/geo+json", "application/geojson", "application/json", None],
    )
    def test_user_token_items_accept_variants(
        self,
        api_client: APIClient,
        owner: User,
        user_token: Token,
        accept_header: str | None,
    ) -> None:
        collection = LandmarkCollection.objects.create(
            name="Readable",
            created_by=owner.email,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=owner,
            level=PermissionLevel.READ_ONLY,
        )
        url = reverse(
            "api:v2:gis-ogc:landmark-collections-user-collection-items",
            kwargs={"key": user_token.key, "collection_id": collection.id},
        )
        if accept_header is None:
            response = api_client.get(url)
        else:
            response = api_client.get(url, HTTP_ACCEPT=accept_header)

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/geo+json"
        assert _streaming_json(response)["type"] == "FeatureCollection"

    def test_user_token_invalid_unknown_inactive_or_inaccessible_404(
        self,
        api_client: APIClient,
        owner: User,
        user_token: Token,
    ) -> None:
        other_user = User.objects.create_user(email="other@example.com")
        unknown_collection_id = "00000000-0000-0000-0000-000000000001"
        inaccessible_collection = LandmarkCollection.objects.create(
            name="Private",
            created_by=other_user.email,
        )
        inactive_collection = LandmarkCollection.objects.create(
            name="Inactive",
            created_by=owner.email,
            is_active=False,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=inactive_collection,
            user=owner,
            level=PermissionLevel.ADMIN,
        )

        invalid_token = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collections-user-collections",
                kwargs={"key": "f" * 40},
            )
        )
        unknown = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collections-user-collection",
                kwargs={
                    "key": user_token.key,
                    "collection_id": unknown_collection_id,
                },
            )
        )
        inactive = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collections-user-collection",
                kwargs={"key": user_token.key, "collection_id": inactive_collection.id},
            )
        )
        inaccessible = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collections-user-collection-items",
                kwargs={
                    "key": user_token.key,
                    "collection_id": inaccessible_collection.id,
                },
            )
        )

        assert invalid_token.status_code == status.HTTP_404_NOT_FOUND
        assert unknown.status_code == status.HTTP_404_NOT_FOUND
        assert inactive.status_code == status.HTTP_404_NOT_FOUND
        assert inaccessible.status_code == status.HTTP_404_NOT_FOUND

    def test_user_token_get_does_not_create_personal_collection(
        self,
        api_client: APIClient,
        owner: User,
        user_token: Token,
    ) -> None:
        """Read-only invariant: OGC GETs must NOT issue a write.

        ``accessible_landmark_collections_queryset`` historically called
        ``get_or_create_personal_landmark_collection`` unconditionally,
        which made every OGC user-token GET produce a CREATE on first
        connect (and a SELECT every time after). This breaks read-replica
        deployments and adds latency on cold start. The OGC service
        opts out via ``ensure_personal=False``; this test pins that
        invariant.
        """
        # Sanity precondition: the user has no personal collection.
        assert not LandmarkCollection.objects.filter(
            collection_type=LandmarkCollection.CollectionType.PERSONAL,
            personal_owner=owner,
        ).exists()

        # Hit the OGC endpoints that go through ``_resolve_collection``
        # / ``list_collections``.
        for url_name in (
            "api:v2:gis-ogc:landmark-collections-user-landing",
            "api:v2:gis-ogc:landmark-collections-user-collections",
        ):
            response = api_client.get(reverse(url_name, kwargs={"key": user_token.key}))
            assert response.status_code == status.HTTP_200_OK

        # Personal collection still does NOT exist — the OGC reads stayed
        # reads.
        assert not LandmarkCollection.objects.filter(
            collection_type=LandmarkCollection.CollectionType.PERSONAL,
            personal_owner=owner,
        ).exists()

    def test_two_landmark_tokens_render_with_distinct_titles(
        self,
        api_client: APIClient,
        owner: User,
    ) -> None:
        """Multiple landmark single-collection tokens added to the same
        ArcGIS Pro / QGIS workspace must be distinguishable.

        OGC clients display the ``title`` field (not the ``id``) in the
        layer table-of-contents. The static id ``landmarks`` is shared
        across single-collection tokens, but each title is the
        collection's own ``name`` — so two different collections render
        as distinct rows in the client UI.
        """
        first = LandmarkCollection.objects.create(
            name="Cave System Alpha",
            created_by=owner.email,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=first,
            user=owner,
            level=PermissionLevel.ADMIN,
        )
        second = LandmarkCollection.objects.create(
            name="Cave System Beta",
            created_by=owner.email,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=second,
            user=owner,
            level=PermissionLevel.ADMIN,
        )

        first_meta = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collection-collection",
                kwargs={
                    "gis_token": first.gis_token,
                    "collection_id": "landmarks",
                },
            )
        )
        second_meta = api_client.get(
            reverse(
                "api:v2:gis-ogc:landmark-collection-collection",
                kwargs={
                    "gis_token": second.gis_token,
                    "collection_id": "landmarks",
                },
            )
        )
        assert first_meta.status_code == status.HTTP_200_OK
        assert second_meta.status_code == status.HTTP_200_OK
        assert first_meta.json()["id"] == "landmarks"
        assert second_meta.json()["id"] == "landmarks"
        # Distinct titles — the disambiguation contract.
        assert first_meta.json()["title"] == "Cave System Alpha"
        assert second_meta.json()["title"] == "Cave System Beta"
        assert first_meta.json()["title"] != second_meta.json()["title"]

    def test_landmark_items_query_count_is_bounded(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
    ) -> None:
        """20 landmarks on one collection: the items endpoint must NOT
        scale linearly with landmark count.

        Baseline math:
        * get_object — 1 query (collection by gis_token)
        * get_collection — 0 queries (scope IS the collection)
        * bbox aggregate — 1 query
        * ETag aggregate — 1 query
        * landmarks list — 1 query (with select_related)

        Cap of 10 catches any per-landmark N+1 (e.g. permission checks
        bleeding into the GeoJSON serializer).
        """
        for i in range(20):
            Landmark.objects.create(
                name=f"Station-{i:02d}",
                description="",
                latitude=45.0 + i * 0.001,
                longitude=-122.0 + i * 0.001,
                created_by=owner.email,
                collection=collection,
            )

        url = reverse(
            "api:v2:gis-ogc:landmark-collection-collection-items",
            kwargs={
                "gis_token": collection.gis_token,
                "collection_id": "landmarks",
            },
        )
        max_queries = 10
        with CaptureQueriesContext(connection) as ctx:
            response = api_client.get(url, HTTP_ACCEPT="application/geo+json")
        assert response.status_code == status.HTTP_200_OK
        # Sanity: all 20 features served.
        payload = _streaming_json(response)
        assert payload["numberMatched"] == 20  # noqa: PLR2004
        actual = len(ctx.captured_queries)
        assert actual <= max_queries, (
            f"Landmark items endpoint issued {actual} queries (cap "
            f"{max_queries}). Likely N+1 from a per-landmark permission "
            f"check in LandmarkGeoJSONSerializer. SQL:\n"
            + "\n".join(q["sql"] for q in ctx.captured_queries)
        )
