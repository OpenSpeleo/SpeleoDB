# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Any

from django.urls import register_converter as _register_converter

from speleodb.surveys.models import FileFormat

if TYPE_CHECKING:
    from collections.abc import Callable


def register_converter(type_name: str) -> Callable[[type[object]], Any]:
    """
    Decorator to register a custom path converter with a given type_name.z
    """

    def decorator(cls: type[Any]) -> Any:
        _register_converter(cls, type_name)
        return cls

    return decorator


class BaseRegexConverter(ABC):
    @property
    @abstractmethod
    def regex(self) -> str: ...

    def to_python(self, value: str) -> str:
        # Validate the hexsha value with the regex
        if not re.match(self.regex, value):
            raise ValueError(f"Invalid value: {value}")
        return value

    def to_url(self, value: str) -> str:
        return value  # Return the value as is for URL generation


@register_converter("gitsha")
class GitSHAConverter(BaseRegexConverter):
    @property
    def regex(self) -> str:
        return r"[0-9a-fA-F]{6,40}"


@register_converter("blobsha")
class BlobSHAConverter(BaseRegexConverter):
    @property
    def regex(self) -> str:
        return r"[0-9a-fA-F]{40}"


class BaseChoicesConverter(BaseRegexConverter):
    choices: list[str]

    @property
    def regex(self) -> str:
        escaped_strings = map(re.escape, self.choices)
        return r"|".join(escaped_strings)


@register_converter("download_format")
class DownloadFormatsConverter(BaseChoicesConverter):
    choices = FileFormat.download_choices


@register_converter("upload_format")
class UploadFormatsConverter(BaseChoicesConverter):
    choices = FileFormat.upload_choices


@register_converter("gis_token")
@register_converter("user_token")
class TokenConverter(BaseRegexConverter):
    @property
    def regex(self) -> str:
        return r"[0-9a-fA-F]{40}"


@register_converter("ogc_typed_id")
class OGCTypedCollectionIdConverter(BaseRegexConverter):
    """OGC API - Features collection id with a geometry-type suffix.

    Project-scoped OGC collections in SpeleoDB are split per geometry
    type so each collection becomes a uniform-geometry GIS layer (the
    universal QGIS / ArcGIS Pro expectation: 1 collection = 1 layer =
    1 geometry type). The collection id is therefore
    ``<commit-sha>_<group>`` where ``<group>`` is currently
    ``points`` (Point + MultiPoint) or ``lines`` (LineString +
    MultiLineString).

    Polygons are not part of this product (cave-survey data does not
    produce them); a future addition is a one-line regex extension
    here plus the matching ``GEOMETRY_GROUPS`` entry in
    ``speleodb/gis/ogc_helpers.py``. The URL routing layer enforces
    the regex so unknown groups 404 at routing time, never reach a
    view, and the legacy mixed ``<sha>`` form is intentionally NOT
    matched here — it is routed separately to a 410 Gone view.
    """

    @property
    def regex(self) -> str:
        return r"[0-9a-fA-F]{6,40}_(?:points|lines)"
