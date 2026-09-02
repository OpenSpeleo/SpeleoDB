# -*- coding: utf-8 -*-

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import ClassVar

from speleodb.gis.gis_layer_processing.common import deterministic_json
from speleodb.gis.gis_layer_processing.types import CompilationResult

if TYPE_CHECKING:
    from typing import Any

    from speleodb.gis.models.gis_layer import GISLayerSourceFormat


class BaseGISLayerProcessor(ABC):
    """Convert one supported GIS source format into renderable GeoJSON."""

    source_format: ClassVar[GISLayerSourceFormat]

    def process(self, source: bytes) -> CompilationResult:
        feature_collection = self.build_feature_collection(source)
        display_geojson = deterministic_json(feature_collection)
        return CompilationResult(display_geojson=display_geojson)

    @abstractmethod
    def build_feature_collection(
        self,
        source: bytes,
    ) -> dict[str, Any]:
        """Return one renderable GeoJSON FeatureCollection."""
