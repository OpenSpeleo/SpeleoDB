"""Read normalized features from storage or an already populated cache."""

from __future__ import annotations

from uuid import uuid4

from django.core.cache import cache
from django.core.files.base import ContentFile

from speleodb.api.v2.views.gis_view import _geojson_cache_key
from speleodb.api.v2.views.gis_view import _load_normalized_features
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import Project


def test_missing_cached_features_are_loaded_from_stored_artifact() -> None:
    artifact = ProjectGeoJSON(project=Project(), commit_id=uuid4().hex)
    artifact.file.save(
        f"{uuid4()}/stored-features.json",
        ContentFile(
            b'{"type":"FeatureCollection","features":[{"type":"Feature",'
            b'"geometry":{"type":"Point","coordinates":[0,0]},'
            b'"properties":{"name":"Stored survey"}}]}'
        ),
        save=False,
    )
    cache_key = _geojson_cache_key(artifact, "features")
    index_key = cache_key.replace(
        "ogc_geojson_features_", "ogc_geojson_features_index_"
    )
    try:
        features = _load_normalized_features(artifact)
        assert len(features) == 1
        assert features[0]["properties"]["name"] == "Stored survey"
    finally:
        cache.delete_many([cache_key, index_key])
        artifact.file.delete(save=False)


def test_available_cached_features_are_used_without_a_storage_object() -> None:
    artifact = ProjectGeoJSON(commit_id=uuid4().hex, file="absent-artifact.json")
    cache_key = _geojson_cache_key(artifact, "features")
    features = [{"id": "cached"}]
    try:
        cache.set(cache_key, features, timeout=30)
        assert _load_normalized_features(artifact) == features
    finally:
        cache.delete(cache_key)
