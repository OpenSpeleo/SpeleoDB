"""Reusable schema declarations for transport envelopes and GeoJSON collections."""

from __future__ import annotations

from functools import cache
from typing import Any

from drf_spectacular.utils import inline_serializer
from rest_framework import serializers


def response_object(
    component_name: str,
    *,
    many: bool = False,
    **fields: serializers.Field[Any, Any, Any, Any],
) -> serializers.Serializer[Any]:
    return inline_serializer(name=component_name, fields=fields, many=many)


@cache
def feature_collection(
    feature_serializer: type[serializers.Serializer[Any]],
) -> serializers.Serializer[Any]:
    return response_object(
        feature_serializer.__name__.removesuffix("Serializer") + "Collection",
        type=serializers.ChoiceField(choices=["FeatureCollection"]),
        features=feature_serializer(many=True),
    )
