# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from typing import Any

import orjson
from django.db.models import Count
from django.db.models import Max
from django.http import Http404
from django.http import HttpResponseNotModified
from django.http import StreamingHttpResponse
from django.urls import reverse
from geojson import FeatureCollection  # type: ignore[attr-defined]
from rest_framework import permissions
from rest_framework.authtoken.models import Token
from rest_framework.generics import GenericAPIView
from rest_framework.renderers import JSONRenderer

from speleodb.api.v2.landmark_access import accessible_landmark_collections_queryset
from speleodb.api.v2.serializers.landmark import LandmarkGeoJSONSerializer
from speleodb.api.v2.views.ogc_base import BaseOGCConformanceApiView
from speleodb.api.v2.views.ogc_base import BaseOGCLandingPageApiView
from speleodb.api.v2.views.ogc_base import GeoJSONRenderer
from speleodb.api.v2.views.ogc_base import LegacyGeoJSONRenderer
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.ogc_models import build_ogc_conformance
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import NoWrapResponse

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from rest_framework.request import Request

    from speleodb.users.models import User

_LANDMARKS_COLLECTION_ID = "landmarks"
_LANDMARK_COLLECTION_CACHE_CONTROL = "public, max-age=60, must-revalidate"


def _host(request: Request) -> str:
    return f"{request.scheme}://{request.get_host().rstrip('/')}"


def _landing_page(request: Request) -> dict[str, Any]:
    host = _host(request)
    base_path = request.path.rstrip("/")

    return {
        "title": "SpeleoDB Landmark Collection",
        "description": "OGC API - Features endpoint for Landmark Point data.",
        "links": [
            {
                "href": f"{host}{base_path}/",
                "rel": "self",
                "type": "application/json",
                "title": "This document",
            },
            {
                "href": f"{host}{base_path}/conformance",
                "rel": "conformance",
                "type": "application/json",
                "title": "Conformance declaration",
            },
            {
                "href": f"{host}{base_path}/collections",
                "rel": "data",
                "type": "application/json",
                "title": "Feature collections",
            },
            {
                "href": f"{host}{reverse('api-schema')}",
                "rel": "service-desc",
                "type": "application/vnd.oai.openapi+json;version=3.0",
                "title": "OpenAPI definition",
            },
        ],
    }


def _user_landing_page(request: Request) -> dict[str, Any]:
    host = _host(request)
    base_path = request.path.rstrip("/")

    return {
        "title": "SpeleoDB Landmark Collections",
        "description": (
            "OGC API - Features endpoint for all active Landmark Collections "
            "the token owner can read."
        ),
        "links": [
            {
                "href": f"{host}{base_path}/",
                "rel": "self",
                "type": "application/json",
                "title": "This document",
            },
            {
                "href": f"{host}{base_path}/conformance",
                "rel": "conformance",
                "type": "application/json",
                "title": "Conformance declaration",
            },
            {
                "href": f"{host}{base_path}/collections",
                "rel": "data",
                "type": "application/json",
                "title": "Feature collections",
            },
            {
                "href": f"{host}{reverse('api-schema')}",
                "rel": "service-desc",
                "type": "application/vnd.oai.openapi+json;version=3.0",
                "title": "OpenAPI definition",
            },
        ],
    }


def _collection_items_etag(collection: LandmarkCollection) -> str:
    agg = collection.landmarks.aggregate(
        latest=Max("modified_date"),
        landmark_count=Count("id"),
    )
    latest_landmark_modified: datetime | None = agg["latest"]
    landmark_count: int = agg["landmark_count"]
    latest_modified = (
        latest_landmark_modified.isoformat() if latest_landmark_modified else ""
    )
    payload = (
        f"{collection.id}:"
        f"{collection.modified_date.isoformat()}:"
        f"{latest_modified}:"
        f"{landmark_count}"
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f'"{digest}"'


def _collection_items_response(
    request: Request,
    collection: LandmarkCollection,
) -> StreamingHttpResponse | HttpResponseNotModified:
    etag = _collection_items_etag(collection)

    if request.headers.get("if-none-match") == etag:
        response_nm = HttpResponseNotModified()
        response_nm["ETag"] = etag
        response_nm["Cache-Control"] = _LANDMARK_COLLECTION_CACHE_CONTROL
        return response_nm

    landmarks = collection.landmarks.select_related("collection").order_by("name")
    serializer = LandmarkGeoJSONSerializer(landmarks, many=True)
    content = orjson.dumps(FeatureCollection(serializer.data))  # type: ignore[no-untyped-call]

    response = StreamingHttpResponse(
        streaming_content=[content],
        content_type="application/geo+json",
    )
    response["ETag"] = etag
    response["Cache-Control"] = _LANDMARK_COLLECTION_CACHE_CONTROL
    response["Content-Disposition"] = "inline"
    return response


def _collection_document(
    host: str,
    collection_path: str,
    collection: LandmarkCollection,
) -> dict[str, Any]:
    collection_id = str(collection.id)
    return {
        "id": collection_id,
        "title": collection.name,
        "description": collection.description or "",
        "itemType": "feature",
        "links": [
            {
                "href": f"{host}{collection_path}",
                "rel": "self",
                "type": "application/json",
                "title": collection.name,
            },
            {
                "href": f"{host}{collection_path}/items",
                "rel": "items",
                "type": "application/geo+json",
                "title": f"{collection.name} Items",
            },
        ],
    }


def _user_collection_or_404(
    user: User,
    collection_id: UUID,
) -> LandmarkCollection:
    try:
        return accessible_landmark_collections_queryset(user=user).get(id=collection_id)
    except LandmarkCollection.DoesNotExist as exc:
        raise Http404(f"Collection `{collection_id}` does not exist.") from exc


class LandmarkCollectionOGCLandingPageApiView(BaseOGCLandingPageApiView):
    """OGC landing page for a public Landmark Collection token."""

    queryset = LandmarkCollection.objects.filter(is_active=True)
    lookup_field = "gis_token"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> NoWrapResponse:
        self.get_object()
        return NoWrapResponse(_landing_page(request=request))


class LandmarkCollectionOGCConformanceApiView(BaseOGCConformanceApiView):
    """OGC conformance declaration for a public Landmark Collection token."""

    queryset = LandmarkCollection.objects.filter(is_active=True)
    lookup_field = "gis_token"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> NoWrapResponse:
        self.get_object()
        return NoWrapResponse(build_ogc_conformance())


class LandmarkCollectionOGCCollectionsApiView(
    GenericAPIView[LandmarkCollection],
    SDBAPIViewMixin,
):
    """OGC collections endpoint for the single Landmark Point layer."""

    schema = None
    permission_classes = [permissions.AllowAny]
    queryset = LandmarkCollection.objects.filter(is_active=True)
    lookup_field = "gis_token"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> NoWrapResponse:
        collection = self.get_object()
        host = _host(request)
        self_path = request.path.rstrip("/")
        collection_path = request.path.rstrip("/")
        landing_path = request.path.rstrip("/").removesuffix("/collections")

        return NoWrapResponse(
            {
                "links": [
                    {
                        "href": f"{host}{self_path}",
                        "rel": "self",
                        "type": "application/json",
                        "title": "Feature Collections",
                    },
                    {
                        "href": f"{host}{self_path}",
                        "rel": "data",
                        "type": "application/json",
                        "title": "Feature Collections",
                    },
                    {
                        "href": f"{host}{landing_path}/",
                        "rel": "root",
                        "type": "application/json",
                        "title": "Landing page",
                    },
                ],
                "collections": [
                    {
                        "id": _LANDMARKS_COLLECTION_ID,
                        "title": collection.name,
                        "description": collection.description or "",
                        "itemType": "feature",
                        "links": [
                            {
                                "href": (
                                    f"{host}{collection_path}/"
                                    f"{_LANDMARKS_COLLECTION_ID}"
                                ),
                                "rel": "self",
                                "type": "application/json",
                                "title": collection.name,
                            },
                            {
                                "href": (
                                    f"{host}{collection_path}/"
                                    f"{_LANDMARKS_COLLECTION_ID}/items"
                                ),
                                "rel": "items",
                                "type": "application/geo+json",
                                "title": f"{collection.name} Items",
                            },
                        ],
                    }
                ],
            }
        )


class LandmarkCollectionOGCCollectionApiView(
    GenericAPIView[LandmarkCollection],
    SDBAPIViewMixin,
):
    """OGC single-collection metadata for Landmark Points."""

    schema = None
    permission_classes = [permissions.AllowAny]
    queryset = LandmarkCollection.objects.filter(is_active=True)
    lookup_field = "gis_token"

    def get(
        self, request: Request, collection_id: str, *args: Any, **kwargs: Any
    ) -> NoWrapResponse:
        if collection_id != _LANDMARKS_COLLECTION_ID:
            raise Http404(f"Collection `{collection_id}` does not exist.")

        collection = self.get_object()
        host = _host(request)
        self_path = request.path.rstrip("/")

        return NoWrapResponse(
            {
                "id": _LANDMARKS_COLLECTION_ID,
                "title": collection.name,
                "description": collection.description,
                "itemType": "feature",
                "links": [
                    {
                        "href": f"{host}{self_path}",
                        "rel": "self",
                        "type": "application/json",
                        "title": collection.name,
                    },
                    {
                        "href": f"{host}{self_path}/items",
                        "rel": "items",
                        "type": "application/geo+json",
                        "title": f"{collection.name} Items",
                    },
                ],
            }
        )


class LandmarkCollectionOGCCollectionItemsApiView(
    GenericAPIView[LandmarkCollection],
    SDBAPIViewMixin,
):
    """OGC ``/items`` endpoint returning dynamic Point GeoJSON."""

    schema = None
    permission_classes = [permissions.AllowAny]
    renderer_classes = [GeoJSONRenderer, LegacyGeoJSONRenderer, JSONRenderer]
    queryset = LandmarkCollection.objects.filter(is_active=True)
    lookup_field = "gis_token"

    def get(
        self,
        request: Request,
        collection_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> StreamingHttpResponse | HttpResponseNotModified:
        if collection_id != _LANDMARKS_COLLECTION_ID:
            raise Http404(f"Collection `{collection_id}` does not exist.")

        collection = self.get_object()
        return _collection_items_response(request=request, collection=collection)


class LandmarkCollectionUserOGCLandingPageApiView(BaseOGCLandingPageApiView):
    """OGC landing page for user-token Landmark Collections."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> NoWrapResponse:
        self.get_object()
        return NoWrapResponse(_user_landing_page(request=request))


class LandmarkCollectionUserOGCConformanceApiView(BaseOGCConformanceApiView):
    """OGC conformance declaration for user-token Landmark Collections."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> NoWrapResponse:
        self.get_object()
        return NoWrapResponse(build_ogc_conformance())


class LandmarkCollectionUserOGCCollectionsApiView(
    GenericAPIView[Token],
    SDBAPIViewMixin,
):
    """OGC collections endpoint for all readable Landmark Collections."""

    schema = None
    permission_classes = [permissions.AllowAny]
    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> NoWrapResponse:
        token = self.get_object()
        host = _host(request)
        url_path = request.path.rstrip("/")
        landing_path = url_path.removesuffix("/collections")
        collections = accessible_landmark_collections_queryset(user=token.user)

        return NoWrapResponse(
            {
                "links": [
                    {
                        "href": f"{host}{url_path}",
                        "rel": "self",
                        "type": "application/json",
                        "title": "Feature Collections",
                    },
                    {
                        "href": f"{host}{url_path}",
                        "rel": "data",
                        "type": "application/json",
                        "title": "Feature Collections",
                    },
                    {
                        "href": f"{host}{landing_path}/",
                        "rel": "root",
                        "type": "application/json",
                        "title": "Landing page",
                    },
                ],
                "collections": [
                    _collection_document(
                        host=host,
                        collection_path=f"{url_path}/{collection.id}",
                        collection=collection,
                    )
                    for collection in collections
                ],
            }
        )


class LandmarkCollectionUserOGCCollectionApiView(
    GenericAPIView[Token],
    SDBAPIViewMixin,
):
    """OGC metadata for one readable user-token Landmark Collection."""

    schema = None
    permission_classes = [permissions.AllowAny]
    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"

    def get(
        self,
        request: Request,
        collection_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> NoWrapResponse:
        token = self.get_object()
        collection = _user_collection_or_404(
            user=token.user,
            collection_id=collection_id,
        )
        host = _host(request)
        self_path = request.path.rstrip("/")

        return NoWrapResponse(
            _collection_document(
                host=host,
                collection_path=self_path,
                collection=collection,
            )
        )


class LandmarkCollectionUserOGCCollectionItemsApiView(
    GenericAPIView[Token],
    SDBAPIViewMixin,
):
    """OGC ``/items`` endpoint for one user-token Landmark Collection."""

    schema = None
    permission_classes = [permissions.AllowAny]
    renderer_classes = [GeoJSONRenderer, LegacyGeoJSONRenderer, JSONRenderer]
    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"

    def get(
        self,
        request: Request,
        collection_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> StreamingHttpResponse | HttpResponseNotModified:
        token = self.get_object()
        collection = _user_collection_or_404(
            user=token.user,
            collection_id=collection_id,
        )
        return _collection_items_response(request=request, collection=collection)
