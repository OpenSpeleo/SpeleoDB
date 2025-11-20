# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import orjson
from django.http import StreamingHttpResponse

if TYPE_CHECKING:
    from collections.abc import Generator

    from speleodb.gis.models import ProjectGeoJSON

logger = logging.getLogger(__name__)


def project_geojsons_to_proxied_response(
    project_geojsons: list[ProjectGeoJSON],
) -> StreamingHttpResponse:
    """Return GeoJSON signed URLs for the view."""

    def geojson_generator() -> Generator[str]:
        yield '{"type":"FeatureCollection","features":['
        first = True
        for geo in project_geojsons:
            with geo.file.open("rb") as f:
                data = orjson.loads(f.read())
                for feature in data.get("features", []):
                    if not first:
                        yield ","
                    yield orjson.dumps(feature).decode("utf-8")
                    first = False
        yield "]}"

    return StreamingHttpResponse(
        geojson_generator(), content_type="application/geo+json"
    )
