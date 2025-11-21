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
        Convert internal layers to an OGC API - Features compliant /collections response
        """

        host = f"{request.scheme}://{request.get_host().rstrip('/')}"
        url_path = request.get_full_path()

        collections = [
            {
                "id": layer.sha,
                "title": layer.title,
                "description": layer.description or "",
                "itemType": "feature",
                "links": [
                    {
                        "href": f"{url_path}/{layer.sha}/",
                        "rel": "items",
                        "type": "application/geo+json",
                        "title": f"{layer.title} Items",
                    }
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
                    "title": "Fake OpenAPI",
                },
                {
                    "href": f"{host}/",
                    "rel": "service-doc",
                    "type": "text/html",
                    "title": "Fake HTML doc",
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
