"""Artifact replacement preserves maps and retires caches without changing Git."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from typing import TYPE_CHECKING
from typing import Any
from unittest.mock import patch

import orjson
import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import connection
from django.db.models import Prefetch
from django.db.models.signals import post_save
from django.http import StreamingHttpResponse
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from speleodb.api.v2.serializers.project import ProjectSerializer
from speleodb.api.v2.serializers.project import ProjectWithGeoJsonSerializer
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.api.v2.views.gis_view import ProjectArtifactOGCService
from speleodb.api.v2.views.gis_view import ProjectViewOGCService
from speleodb.api.v2.views.gis_view import _geojson_cache_key
from speleodb.api.v2.views.gis_view import _load_collection_bbox
from speleodb.api.v2.views.gis_view import _load_feature_by_id
from speleodb.api.v2.views.gis_view import _load_geometry_groups_present
from speleodb.api.v2.views.gis_view import _load_normalized_features
from speleodb.api.v2.views.project_geojson import ProjectUserOGCService
from speleodb.background_jobs.archive import _snapshot_sources
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISProjectView
from speleodb.gis.models import GISView
from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.project_geojson_services import replace_project_geojson
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit

if TYPE_CHECKING:
    from pathlib import Path

    from speleodb.users.models import User


POINT_DATA: dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [1, 2]},
            "properties": {"id": "entrance"},
        }
    ],
}
LINE_DATA: dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[3, 4], [5, 6]]},
            "properties": {"id": "shot", "color": "#123456"},
        }
    ],
}


@pytest.fixture
def artifact_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> FileSystemStorage:
    storage = FileSystemStorage(location=tmp_path, base_url="/test-artifacts/")
    field = ProjectGeoJSON._meta.get_field("file")  # noqa: SLF001
    monkeypatch.setattr(field, "storage", storage)
    return storage


@pytest.fixture
def artifact(project: Project, artifact_storage: FileSystemStorage) -> ProjectGeoJSON:
    commit = ProjectCommit.objects.create(
        id="a" * 40,
        project=project,
        author_name="Test",
        author_email="test@example.com",
        authored_date=timezone.now(),
        message="Survey source",
    )
    return replace_project_geojson(project, commit, POINT_DATA)


@pytest.mark.django_db
def test_replacement_changes_revision_and_preserves_pinned_view(
    artifact: ProjectGeoJSON,
    artifact_storage: FileSystemStorage,
    user: User,
    caplog: pytest.LogCaptureFixture,
) -> None:
    old_name = artifact.file.name
    assert old_name is not None
    revision = artifact.geojson_revision
    view = GISView.objects.create(name="Pinned", owner=user, allow_precise_zoom=False)
    membership = GISProjectView.objects.create(
        gis_view=view, project=artifact.project, commit_sha=artifact.commit_id
    )
    with (
        caplog.at_level("INFO", logger="speleodb.gis.project_geojson_services"),
        TestCase.captureOnCommitCallbacks(execute=True),
    ):
        replacement = replace_project_geojson(
            artifact.project, artifact.commit, LINE_DATA
        )
        assert artifact_storage.exists(old_name)
    assert artifact_storage.exists(old_name)
    assert f"Retained retired GeoJSON object {old_name}" in caplog.text
    with artifact.file.open("rb") as source:
        assert orjson.loads(source.read()) == POINT_DATA
    assert replacement.pk == artifact.pk
    assert replacement.geojson_revision != revision
    assert replacement.file.name is not None
    assert (
        replacement.geojson_revision
        == sha256(replacement.file.name.encode("utf-8")).hexdigest()
    )
    membership.refresh_from_db()
    assert membership.commit_sha == artifact.commit_id
    assert ProjectCommit.objects.filter(pk=artifact.commit_id).exists()
    with replacement.file.open("rb") as source:
        assert orjson.loads(source.read()) == LINE_DATA


@pytest.mark.django_db
def test_invalid_replacement_keeps_previous_artifact(
    artifact: ProjectGeoJSON, artifact_storage: FileSystemStorage
) -> None:
    with pytest.raises(ValidationError):
        replace_project_geojson(
            artifact.project, artifact.commit, {"type": "not GeoJSON"}
        )
    artifact.refresh_from_db()
    assert artifact.file.name is not None
    assert artifact_storage.exists(artifact.file.name)
    with artifact.file.open("rb") as source:
        assert orjson.loads(source.read()) == POINT_DATA


@pytest.mark.django_db
def test_failed_insert_rolls_back_row_and_removes_new_blob(
    artifact: ProjectGeoJSON, artifact_storage: FileSystemStorage, tmp_path: Path
) -> None:
    previous_files = set(tmp_path.rglob("*.json"))

    def reject_insert(sender: type[ProjectGeoJSON], **kwargs: Any) -> None:
        raise RuntimeError("Reject replacement after database insert")

    post_save.connect(reject_insert, sender=ProjectGeoJSON)
    try:
        with pytest.raises(RuntimeError, match="after database insert"):
            replace_project_geojson(artifact.project, artifact.commit, LINE_DATA)
    finally:
        post_save.disconnect(reject_insert, sender=ProjectGeoJSON)
    old_revision = artifact.geojson_revision
    artifact.refresh_from_db()
    assert artifact.geojson_revision == old_revision
    assert artifact.file.name is not None
    assert artifact_storage.exists(artifact.file.name)
    assert set(tmp_path.rglob("*.json")) == previous_files


@pytest.mark.django_db
def test_upload_failure_keeps_previous_artifact(
    artifact: ProjectGeoJSON,
    artifact_storage: FileSystemStorage,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A real filesystem failure: the proposed storage root is an ordinary file.
    blocked_root = tmp_path / "blocked"
    blocked_root.write_text("not a directory", encoding="utf-8")
    field = ProjectGeoJSON._meta.get_field("file")  # noqa: SLF001
    monkeypatch.setattr(field, "storage", FileSystemStorage(location=blocked_root))
    with pytest.raises(NotADirectoryError):
        replace_project_geojson(artifact.project, artifact.commit, LINE_DATA)
    assert ProjectGeoJSON.objects.get(pk=artifact.pk).geojson_revision == (
        artifact.geojson_revision
    )
    assert artifact.file.name is not None
    assert artifact_storage.exists(artifact.file.name)


@pytest.mark.django_db
def test_all_ogc_caches_use_artifact_revision(artifact: ProjectGeoJSON) -> None:
    cache.clear()
    assert _load_geometry_groups_present(artifact.commit_id) == frozenset({"points"})
    assert _load_collection_bbox(artifact.commit_id, "points") == (1, 2, 1, 2)
    assert _load_feature_by_id(artifact.commit_id, "entrance", "points") is not None
    old_features_key = _geojson_cache_key(artifact, "features")
    assert cache.get(old_features_key) is not None
    with TestCase.captureOnCommitCallbacks(execute=True):
        replacement = replace_project_geojson(
            artifact.project, artifact.commit, LINE_DATA
        )
    with patch.object(cache, "add", wraps=cache.add) as add:
        assert _load_geometry_groups_present(artifact.commit_id) == frozenset({"lines"})
    add.assert_called_once_with(
        f"{_geojson_cache_key(replacement, 'features')}:lock", "1", timeout=60
    )
    assert _load_collection_bbox(artifact.commit_id, "lines") == (3, 4, 5, 6)
    assert _load_collection_bbox(artifact.commit_id, "points") is None
    assert _load_feature_by_id(artifact.commit_id, "entrance", "points") is None
    shot = _load_feature_by_id(artifact.commit_id, "shot", "lines")
    assert shot is not None
    assert shot["properties"]["color"] == "#123456"
    # A late reader holding the old snapshot can fill only the old namespace.
    cache.delete(old_features_key)
    old_features = _load_normalized_features(artifact)
    assert old_features[0]["geometry"]["type"] == "Point"
    assert _load_normalized_features(artifact.commit_id) == [shot]


@pytest.mark.django_db
def test_project_metadata_pairs_revision_and_url_without_extra_queries(
    artifact: ProjectGeoJSON,
) -> None:
    project = Project.objects.prefetch_related(
        Prefetch(
            "geojsons",
            queryset=ProjectGeoJSON.objects.order_by("-commit__authored_date"),
        )
    ).get(pk=artifact.project_id)
    # Isolate the added metadata from unrelated base project serializer queries.
    with (
        patch.object(ProjectSerializer, "to_representation", return_value={}),
        patch.object(
            ProjectGeoJSON, "get_signed_download_url", side_effect=["first", "renewed"]
        ),
        CaptureQueriesContext(connection) as queries,
    ):
        first = ProjectWithGeoJsonSerializer(project).data
        renewed = ProjectWithGeoJsonSerializer(project).data
    assert len(queries) == 0
    assert first["geojson_commit_sha"] == artifact.commit_id
    assert renewed["geojson_commit_sha"] == artifact.commit_id
    assert first["geojson_file"] == "first"
    assert renewed["geojson_file"] == "renewed"
    assert (
        first["geojson_revision"]
        == renewed["geojson_revision"]
        == artifact.geojson_revision
    )


@pytest.mark.django_db
def test_project_metadata_without_artifact_is_null(project: Project) -> None:
    with patch.object(ProjectSerializer, "to_representation", return_value={}):
        data = ProjectWithGeoJsonSerializer(project).data
    assert data["geojson_file"] is None
    assert data["geojson_revision"] is None
    assert data["geojson_commit_sha"] is None


@pytest.mark.django_db
def test_latest_map_order_agrees_for_ogc_authorization_and_archive(
    artifact: ProjectGeoJSON, user: User
) -> None:
    newer = ProjectCommit.objects.create(
        id="0" * 40,
        project=artifact.project,
        author_name="Test",
        author_email="test@example.com",
        authored_date=artifact.commit.authored_date,
        message="New source with the same Git timestamp",
    )
    latest = replace_project_geojson(artifact.project, newer, POINT_DATA)
    # The older source completes last; its artifact timestamp must not win.
    ProjectGeoJSON.objects.filter(pk=artifact.pk).update(
        creation_date=latest.creation_date + timedelta(seconds=1)
    )
    UserProjectPermissionFactory(
        target=user, project=artifact.project, level=PermissionLevel.READ_ONLY
    )
    view = GISView.objects.create(name="Latest", owner=user, allow_precise_zoom=False)
    GISProjectView.objects.create(
        gis_view=view, project=artifact.project, use_latest=True
    )
    service = ProjectViewOGCService()
    collection_id = f"{newer.pk}_points"
    assert [item.id for item in service.list_collections(view)] == [collection_id]
    assert service.get_collection(view, collection_id) is not None
    assert service.get_collection(view, f"{artifact.commit_id}_points") is None
    sources, _ = _snapshot_sources(user)
    selected = [source for source in sources if source.category == "geojsons"]
    assert len(selected) == 1
    assert selected[0].resource.pk == newer.pk


@pytest.mark.django_db
def test_nonforced_generation_keeps_artifact_created_during_processing(
    artifact: ProjectGeoJSON, tmp_path: Path
) -> None:
    previous_files = set(tmp_path.rglob("*.json"))
    result = replace_project_geojson(
        artifact.project, artifact.commit, LINE_DATA, replace_existing=False
    )
    assert result.geojson_revision == artifact.geojson_revision
    assert set(tmp_path.rglob("*.json")) == previous_files


@pytest.mark.django_db
def test_repeated_rebuild_never_reuses_an_artifact_revision(
    artifact: ProjectGeoJSON,
) -> None:
    revisions = {artifact.geojson_revision}
    for _ in range(3):
        with TestCase.captureOnCommitCallbacks(execute=True):
            artifact = replace_project_geojson(
                artifact.project, artifact.commit, LINE_DATA
            )
        assert artifact.geojson_revision not in revisions
        revisions.add(artifact.geojson_revision)


@pytest.fixture(params=["view", "user"])
def ogc_scope(
    request: pytest.FixtureRequest, artifact: ProjectGeoJSON, user: User
) -> tuple[ProjectArtifactOGCService[Any], GISView | Token, str]:
    collection_id = f"{artifact.commit_id}_points"
    if request.param == "view":
        view = GISView.objects.create(
            name="Artifact revisions", owner=user, allow_precise_zoom=False
        )
        GISProjectView.objects.create(
            gis_view=view, project=artifact.project, commit_sha=artifact.commit_id
        )
        return (
            ProjectViewOGCService(),
            view,
            reverse(
                "api:v2:gis-ogc:view-collection-items",
                kwargs={"gis_token": view.gis_token, "collection_id": collection_id},
            ),
        )
    UserProjectPermissionFactory(
        target=user, level=PermissionLevel.READ_ONLY, project=artifact.project
    )
    token, _ = Token.objects.get_or_create(user=user)
    return (
        ProjectUserOGCService(),
        token,
        reverse(
            "api:v2:gis-ogc:user-collection-items",
            kwargs={"key": token.key, "collection_id": collection_id},
        ),
    )


@pytest.mark.django_db
def test_ogc_snapshot_pairs_etag_metadata_and_payload_across_replacement(
    artifact: ProjectGeoJSON,
    ogc_scope: tuple[ProjectArtifactOGCService[Any], GISView | Token, str],
) -> None:
    service, scope, _ = ogc_scope
    collection_id = f"{artifact.commit_id}_points"
    meta = service.get_collection(scope, collection_id)
    assert meta is not None
    assert meta.bbox == (1, 2, 1, 2)
    etag = service.get_etag(scope, collection_id)
    assert etag == f"{collection_id}_{artifact.geojson_revision}"
    new_data = deepcopy(POINT_DATA)
    new_data["features"][0]["geometry"]["coordinates"] = [3, 4]
    with TestCase.captureOnCommitCallbacks(execute=True):
        replacement = replace_project_geojson(
            artifact.project, artifact.commit, new_data
        )
    # Cold reads after commit still open the retired immutable blob, even if
    # replacement lands between generic-view metadata, ETag and payload calls.
    cache.clear()
    features = service.get_features(scope, collection_id)
    assert features[0]["geometry"]["coordinates"] == [1, 2]
    assert service.get_feature(scope, collection_id, "entrance") == features[0]
    assert service.get_etag(scope, collection_id) == etag
    fresh_service = type(service)()
    assert fresh_service.get_etag(scope, collection_id) == (
        f"{collection_id}_{replacement.geojson_revision}"
    )
    assert fresh_service.get_features(scope, collection_id)[0]["geometry"][
        "coordinates"
    ] == [3, 4]


@pytest.mark.django_db
@pytest.mark.parametrize("single_feature", [False, True])
def test_ogc_same_commit_replacement_revalidates_http_etag(
    artifact: ProjectGeoJSON,
    ogc_scope: tuple[ProjectArtifactOGCService[Any], GISView | Token, str],
    single_feature: bool,
) -> None:
    _, _, url = ogc_scope
    if single_feature:
        url += "/entrance"
    client = APIClient()
    before = client.get(url)
    assert before.status_code == 200  # noqa: PLR2004
    old_etag = before["ETag"]
    new_data = deepcopy(POINT_DATA)
    new_data["features"][0]["geometry"]["coordinates"] = [3, 4]
    with TestCase.captureOnCommitCallbacks(execute=True):
        replacement = replace_project_geojson(
            artifact.project, artifact.commit, new_data
        )
    after = client.get(url, headers={"if-none-match": old_etag})
    assert after.status_code == 200  # noqa: PLR2004
    assert isinstance(after, StreamingHttpResponse)
    assert after["ETag"] == (
        f'"{artifact.commit_id}_points_{replacement.geojson_revision}"'
    )
    assert after["ETag"] != old_etag
    payload = orjson.loads(b"".join(after.streaming_content))
    if not single_feature:
        payload = payload["features"][0]
    assert payload["geometry"]["coordinates"] == [3, 4]
    if not single_feature:
        unchanged = client.get(url, headers={"if-none-match": after["ETag"]})
        assert unchanged.status_code == 304  # noqa: PLR2004
