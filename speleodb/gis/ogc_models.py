from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.urls import reverse
from pydantic import BaseModel
from pydantic import Field
from pydantic import HttpUrl

if TYPE_CHECKING:
    from typing import Any

    from rest_framework.request import Request


# ---------------------------------------------------------------------------
# OGC API - Features conformance classes (minimal / static dataset)
# ---------------------------------------------------------------------------
OGC_CONFORMANCE_CLASSES: list[str] = [
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
]


def build_ogc_landing_page(request: Request) -> dict[str, Any]:
    """Build an OGC API - Features compliant landing page response.

    QGIS discovers the service by fetching this document and following
    the ``rel: data`` link to the collections endpoint and the
    ``rel: conformance`` link to the conformance declaration.
    """
    host = f"{request.scheme}://{request.get_host().rstrip('/')}"
    # Base path without trailing slash - e.g. /api/v1/gis-ogc/view/<token>
    base_path = request.path.rstrip("/")

    return {
        "title": "SpeleoDB GIS",
        "description": "OGC API - Features endpoint for SpeleoDB GIS data.",
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
                "href": f"{host}{base_path}",
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


def build_ogc_conformance() -> dict[str, list[str]]:
    """Build an OGC API - Features conformance declaration.

    Only ``core`` and ``geojson`` are declared — no filtering, no CRS
    negotiation, no tiling.  This tells GIS clients that the server is a
    simple static feature provider.
    """
    return {"conformsTo": OGC_CONFORMANCE_CLASSES}


class OGCLayer(BaseModel):
    sha: str = Field(
        min_length=40,  # Git commit hashes are typically at least 7 characters long
        max_length=40,  # Full commit hashes are 40 characters long
        pattern=r"^[0-9a-f]+$",  # Ensure it's a hexadecimal string
        description="The Git commit hash for the source code.",
    )
    title: str
    description: str | None = None
    url: HttpUrl


class OGCLayerList(BaseModel):
    layers: list[OGCLayer]

    def to_ogc_collections(self, request: Request) -> dict[str, Any]:
        """
        Convert internal layers to an OGC API - Features ``/collections``
        response.

        Each collection includes a ``rel: self`` link to its own metadata
        and a ``rel: items`` link pointing to the ``/items`` endpoint that
        serves the GeoJSON directly.
        """

        host = f"{request.scheme}://{request.get_host().rstrip('/')}"
        url_path = request.get_full_path().rstrip("/")

        collections = [
            {
                "id": layer.sha,
                "title": layer.title,
                "description": layer.description or "",
                "itemType": "feature",
                "links": [
                    {
                        "href": f"{host}{url_path}/{layer.sha}",
                        "rel": "self",
                        "type": "application/json",
                        "title": layer.title,
                    },
                    {
                        "href": f"{host}{url_path}/{layer.sha}/items",
                        "rel": "items",
                        "type": "application/geo+json",
                        "title": f"{layer.title} Items",
                    },
                ],
            }
            for layer in self.layers
        ]

        return {
            "links": [
                {
                    "href": f"{host}{url_path}",
                    "rel": "self",
                    "type": "application/json",
                    "title": "Feature Collections",
                },
                {
                    "href": f"{host}{reverse('api-schema')}",
                    "rel": "service-desc",
                    "type": "application/vnd.oai.openapi+json;version=3.0",
                    "title": "OpenAPI definition",
                },
                {
                    "href": f"{host}{url_path}",
                    "rel": "data",
                    "type": "application/json",
                    "title": "Feature Collections",
                },
            ],
            "collections": collections,
        }
