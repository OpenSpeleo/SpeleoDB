# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LandmarkCandidate:
    name: str
    description: str
    longitude: float
    latitude: float


@dataclass(frozen=True, slots=True)
class KMLWarning:
    code: str
    message: str
    count: int
    modes: tuple[str, ...] = ("places", "overlay")

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "count": self.count,
            "modes": list(self.modes),
        }


@dataclass(frozen=True, slots=True)
class KMLAnalysis:
    feature_collection: dict[str, Any]
    display_geojson: bytes
    landmark_candidates: tuple[LandmarkCandidate, ...]
    source_placemarks: int
    eligible_placemarks: int
    overlay_placemarks: int
    point_parts: int
    line_parts: int
    polygon_parts: int
    warnings: tuple[KMLWarning, ...]

    def inspection(self) -> dict[str, Any]:
        """Return bounded metadata, never uploaded coordinates or descriptions."""
        point_count = len(self.landmark_candidates)
        unique_count = len(
            {(point.longitude, point.latitude) for point in self.landmark_candidates}
        )
        return {
            "source_placemarks": self.source_placemarks,
            "places": {
                "eligible_placemarks": self.eligible_placemarks,
                "point_count": point_count,
                "unique_coordinate_count": unique_count,
                "duplicate_coordinate_count": point_count - unique_count,
                "skipped_placemarks": self.source_placemarks - self.eligible_placemarks,
            },
            "overlay": {
                "source_placemarks": self.overlay_placemarks,
                "feature_count": len(self.feature_collection["features"]),
                "point_parts": self.point_parts,
                "line_parts": self.line_parts,
                "polygon_parts": self.polygon_parts,
            },
            "warnings": [warning.as_dict() for warning in self.warnings],
        }


@dataclass(frozen=True, slots=True)
class CompilationResult:
    display_geojson: bytes
