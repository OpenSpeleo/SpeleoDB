# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompilationResult:
    display_geojson: bytes
