"""Archive contracts exercised with real SQL, configured S3, GitLab, and Git."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import time
from datetime import timedelta
from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING
from zipfile import ZipFile

import gitlab
import orjson
import pytest
from django.conf import settings as django_settings
from django.core.files.base import ContentFile
from django.utils import timezone

from speleodb.api.v2.tests.factories import ProjectCommitFactory
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import SurveyTeamFactory
from speleodb.api.v2.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v2.tests.factories import TeamProjectPermissionFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.background_jobs.archive import ARCHIVE_DIRECTORIES
from speleodb.background_jobs.archive import _snapshot_sources
from speleodb.background_jobs.archive import _write_file
from speleodb.background_jobs.archive import build_archive
from speleodb.background_jobs.archive_sources import ArchiveBuildError
from speleodb.background_jobs.archive_sources import GitSource
from speleodb.background_jobs.archive_sources import SourceUnavailableError
from speleodb.background_jobs.archive_sources import download_source
from speleodb.background_jobs.archive_sources import mirror_project
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISLayer
from speleodb.gis.models import GISLayerUserPermission
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import GPSTrackUserPermission
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission
from speleodb.gis.models import ProjectGeoJSON
from speleodb.git_engine.client import GitlabClient
from speleodb.testing.gitlab_audit import creation_allocation
from speleodb.testing.gitlab_lifecycle import assert_initial_commit_lifecycle
from speleodb.testing.gitlab_lifecycle import assert_remote_deleted
from speleodb.testing.gitlab_lifecycle import cleanup_remote_on_exit
from speleodb.testing.gitlab_pool import canonical_project
from speleodb.testing.gitlab_pool import get_pool
from speleodb.utils.s3_storages import GeoJSONStorage

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Generator
    from pathlib import Path

    from django.core.files.storage import Storage
    from gitlab.v4.objects.commits import ProjectCommit as GitlabCommit
    from gitlab.v4.objects.projects import Project as GitlabProject
    from pytest_django.fixtures import Settings

    from speleodb.surveys.models import Project
    from speleodb.users.models import User


type SourceWriter = Callable[[Storage, str, bytes], str]

INITIAL_COMMIT_ATTEMPTS: int = 5

EMPTY_GEOJSON: bytes = b'{"type":"FeatureCollection","features":[]}'
OLD_GEOJSON: bytes = b'{"type":"FeatureCollection","features":[],"version":"old"}'
LATEST_GEOJSON: bytes = b'{"type":"FeatureCollection","features":[],"version":"latest"}'

TRACK_GEOJSON: bytes = orjson.dumps(
    {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-87.2, 20.1, 2], [-87.3, 20.2, 3]],
                },
                "properties": {},
            }
        ],
    }
)


@pytest.fixture
def write_source() -> Generator[SourceWriter]:
    """Write and remove real objects in the configured isolated test bucket."""
    written: list[tuple[Storage, str]] = []

    def write(storage: Storage, name: str, data: bytes) -> str:
        key: str = storage.save(name, ContentFile(data))
        written.append((storage, key))
        return key

    yield write
    for storage, key in written:
        storage.delete(key)


def _track(
    user: User, write_source: SourceWriter, *, data: bytes = TRACK_GEOJSON
) -> GPSTrack:
    track = GPSTrack(name="Test track", created_by=user.email)
    track.file = write_source(track.file.storage, f"{track.id}.geojson", data)
    track.save()
    GPSTrackUserPermission.objects.create(user=user, gps_track=track)
    return track


def _collection(user: User, *, name: str = "Collection") -> LandmarkCollection:
    collection = LandmarkCollection.objects.create(name=name, created_by=user.email)
    LandmarkCollectionUserPermission.objects.create(user=user, collection=collection)
    return collection


def _git(directory: Path, *arguments: str) -> str:
    executable: str | None = shutil.which("git")
    assert executable is not None
    environment: dict[str, str] = os.environ | {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "Export test",
        "GIT_COMMITTER_NAME": "Export test",
        "GIT_AUTHOR_EMAIL": "export@test.local",
        "GIT_COMMITTER_EMAIL": "export@test.local",
    }
    result = subprocess.run(  # noqa: S603
        [executable, *arguments],
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()


@pytest.fixture
def git_repository(tmp_path: Path) -> tuple[Path, str, str]:
    repository: Path = tmp_path / "remote"
    repository.mkdir()
    _git(repository, "init", "--initial-branch=main")
    (repository / "survey.txt").write_text("historic data", encoding="utf-8")
    _git(repository, "add", "survey.txt")
    _git(repository, "commit", "-m", "First survey")
    historical: str = _git(repository, "rev-parse", "HEAD")
    _git(repository, "tag", "historic-tag")
    _git(repository, "branch", "survey-branch")
    (repository / "survey.txt").write_text("current data", encoding="utf-8")
    _git(repository, "commit", "-am", "Updated survey")
    return repository, historical, _git(repository, "rev-parse", "HEAD")


@pytest.fixture
def gitlab_client() -> Generator[GitlabClient]:
    client: GitlabClient = GitlabClient(
        f"{django_settings.GITLAB_HTTP_PROTOCOL}://{django_settings.GITLAB_HOST_URL}",
        private_token=django_settings.GITLAB_TOKEN,
        keep_base_url=django_settings.GITLAB_HTTP_PROTOCOL == "http",
    )
    try:
        client.auth()
        assert client.user is not None
        group = client.groups.get(str(django_settings.GITLAB_GROUP_ID))
        assert group.full_path == django_settings.GITLAB_GROUP_NAME
        yield client
    finally:
        client.session.close()


@pytest.fixture
def gitlab_project(
    user: User, gitlab_client: gitlab.Gitlab
) -> tuple[Project, str, str]:
    """Lease existing history; never provision a repository for each export."""
    project: Project = canonical_project(PermissionLevel.READ_ONLY)
    UserProjectPermissionFactory.create(
        target=user, project=project, level=PermissionLevel.READ_ONLY
    )
    get_pool().prepare(project)
    remote = gitlab_client.projects.get(
        f"{django_settings.GITLAB_GROUP_NAME}/{project.id}"
    )
    remote.branches.create(
        {"branch": "main", "ref": django_settings.DJANGO_GIT_BRANCH_NAME}
    )
    historical: str = _create_initial_gitlab_commit(remote)
    remote.tags.create({"tag_name": "historic-tag", "ref": historical})
    remote.branches.create({"branch": "survey-branch", "ref": historical})
    latest = remote.commits.create(
        {
            "branch": "main",
            "commit_message": "Current survey",
            "actions": [
                {
                    "action": "update",
                    "file_path": "survey.txt",
                    "content": "current data",
                }
            ],
        }
    )
    remote.default_branch = "main"
    remote.save()
    return project, historical, str(latest.id)


def _create_initial_gitlab_commit(remote: GitlabProject) -> str:
    """Allow a newly created project's commit endpoint time to become visible."""
    attempt: int = 0
    while True:
        attempt += 1
        try:
            initial: GitlabCommit = remote.commits.create(
                {
                    "branch": "main",
                    "commit_message": "Historic survey",
                    "actions": [
                        {
                            "action": "create",
                            "file_path": "survey.txt",
                            "content": "historic data",
                        }
                    ],
                }
            )
            return str(initial.id)
        except gitlab.exceptions.GitlabCreateError as error:
            # The project was just created successfully. Only an explicit 404
            # is replayable here; other failures may have applied the commit.
            if (
                error.response_code != HTTPStatus.NOT_FOUND
                or attempt == INITIAL_COMMIT_ATTEMPTS
            ):
                raise
            time.sleep(2 ** (attempt - 1))


def _progress(stage: str, completed: int, total: int) -> None:
    assert stage
    assert 0 <= completed <= total


def _restore_and_verify(
    repository: Path, *, destination: Path, historical: str, current: str
) -> None:
    assert (repository / ".git").is_dir()
    assert (repository / "survey.txt").read_text() == "current data"
    assert _git(repository, "status", "--porcelain") == ""
    assert _git(repository, "rev-parse", "HEAD") == current
    assert _git(repository, "symbolic-ref", "HEAD") == "refs/heads/main"
    assert _git(repository, "rev-parse", "refs/heads/main") == current
    assert _git(repository, "rev-parse", "refs/tags/historic-tag") == historical
    assert _git(repository, "rev-parse", "refs/heads/survey-branch") == historical
    _git(repository, "fsck", "--full")
    _git(destination.parent, "clone", str(repository), str(destination))
    assert _git(destination, "show", f"{historical}:survey.txt") == "historic data"
    assert (destination / "survey.txt").read_text() == "current data"


@pytest.mark.django_db
def test_empty_export_does_not_materialize_personal_collection(
    user: User, tmp_path: Path
) -> None:
    destination: Path = tmp_path / "export.zip"
    result = build_archive(user=user, destination=destination, progress=_progress)
    assert result.partial is False
    assert not LandmarkCollection.objects.filter(personal_owner=user).exists()
    assert result.manifest["selected_resources"] == 0
    with ZipFile(destination) as archive:
        assert set(ARCHIVE_DIRECTORIES).issubset(archive.namelist())
        assert archive.testzip() is None
        assert orjson.loads(archive.read("manifest.json")) == result.manifest
    assert result.sha256 == hashlib.sha256(destination.read_bytes()).hexdigest()


@pytest.mark.django_db
@pytest.mark.skip_if_lighttest
def test_complete_archive_preserves_sources_and_git_history(
    user: User,
    tmp_path: Path,
    write_source: SourceWriter,
    gitlab_project: tuple[Project, str, str],
) -> None:
    project, historical, current = gitlab_project
    # The worker must fetch full history even without any application checkout.
    assert not project.git_repo_dir.exists()
    old = ProjectCommitFactory.create(
        id=historical, project=project, authored_date=timezone.now() - timedelta(days=1)
    )
    latest = ProjectCommitFactory.create(
        id=current, project=project, authored_date=timezone.now()
    )
    storage = GeoJSONStorage()
    ProjectGeoJSON.objects.bulk_create(
        [
            ProjectGeoJSON(
                project=project,
                commit=old,
                file=write_source(storage, f"{project.id}/{old.id}.json", OLD_GEOJSON),
            ),
            ProjectGeoJSON(
                project=project,
                commit=latest,
                file=write_source(
                    storage, f"{project.id}/{latest.id}.json", LATEST_GEOJSON
                ),
            ),
        ]
    )
    layer = GISLayer(name="Geology", created_by=user.email)
    layer.source_f = write_source(
        layer.source_f.storage, f"{layer.id}/source.kml", b"<kml/>"
    )
    layer.data_f = write_source(
        layer.data_f.storage, f"{layer.id}/processed.geojson", EMPTY_GEOJSON
    )
    layer.save()
    GISLayerUserPermission.objects.create(user=user, gis_layer=layer)
    _track(user, write_source)
    collection = _collection(user)
    landmark = Landmark.objects.create(
        name="Entrance",
        collection=collection,
        created_by=user.email,
        latitude=20,
        longitude=-87,
    )
    _collection(user, name="Empty")
    destination: Path = tmp_path / "export.zip"
    result = build_archive(user=user, destination=destination, progress=_progress)
    assert result.partial is False
    assert not project.git_repo_dir.exists()
    with ZipFile(destination) as archive:
        assert archive.testzip() is None
        geojson_name = next(
            name
            for name in archive.namelist()
            if name.startswith("geojsons/") and name.endswith(".geojson")
        )
        assert archive.read(geojson_name) == LATEST_GEOJSON
        token: bytes = str(django_settings.GITLAB_TOKEN).encode()
        assert token
        assert all(token not in archive.read(name) for name in archive.namelist())
        assert any(
            archive.read(name) == b"<kml/>"
            for name in archive.namelist()
            if name.endswith(".kml")
        )
        gpx_name = next(name for name in archive.namelist() if name.endswith(".gpx"))
        gpx: bytes = archive.read(gpx_name)
        assert b'creator="SpeleoDB"' in gpx
        assert b'version="1.1"' in gpx
        assert b"http://www.topografix.com/GPX/1/1" in gpx
        collections = [
            orjson.loads(archive.read(name))
            for name in archive.namelist()
            if name.startswith("landmarks/") and name.endswith(".geojson")
        ]
        feature = next(c["features"][0] for c in collections if c["features"])
        assert feature["id"] == str(landmark.id)
        assert feature["geometry"]["coordinates"] == [-87, 20]
        assert "modified_date" in feature["properties"]
        assert "can_write" not in feature["properties"]
        assert all("gis_token" not in c for c in collections)
        for resource in result.manifest["resources"]:
            for entry in resource["files"]:
                data: bytes = archive.read(entry["path"])
                assert entry["sha256"] == hashlib.sha256(data).hexdigest()
                assert entry["size_bytes"] == len(data)
        archive.extractall(tmp_path / "restored")
    repository = next((tmp_path / "restored" / "projects").glob("*/.git")).parent
    _restore_and_verify(
        repository,
        destination=tmp_path / "working",
        historical=historical,
        current=current,
    )


@pytest.mark.django_db
def test_project_permissions_are_filtered_and_deduplicated(user: User) -> None:
    readable: Project = ProjectFactory.create()
    viewer: Project = ProjectFactory.create()
    inactive: Project = ProjectFactory.create(is_active=False)
    revoked: Project = ProjectFactory.create()
    team_only: Project = ProjectFactory.create()
    inactive_membership: Project = ProjectFactory.create()
    for project, level, active in (
        (readable, PermissionLevel.READ_ONLY, True),
        (viewer, PermissionLevel.WEB_VIEWER, True),
        (inactive, PermissionLevel.ADMIN, True),
        (revoked, PermissionLevel.ADMIN, False),
    ):
        UserProjectPermissionFactory.create(
            target=user, project=project, level=level, is_active=active
        )
    team = SurveyTeamFactory.create()
    SurveyTeamMembershipFactory.create(user=user, team=team)
    TeamProjectPermissionFactory.create(target=team, project=readable)
    TeamProjectPermissionFactory.create(target=team, project=team_only)
    other_team = SurveyTeamFactory.create()
    SurveyTeamMembershipFactory.create(user=user, team=other_team, is_active=False)
    TeamProjectPermissionFactory.create(target=other_team, project=inactive_membership)
    sources, notes = _snapshot_sources(user)
    ids: list[str] = [source.resource_id for source in sources]
    assert set(ids) == {str(readable.id), str(team_only.id)}
    assert len(ids) == len(set(ids))
    assert len(notes) == len(ids)


@pytest.mark.django_db
def test_permission_snapshot_survives_revocation_and_deactivation(
    user: User,
    tmp_path: Path,
    write_source: SourceWriter,
) -> None:
    track = _track(user, write_source)
    collection = _collection(user)

    def revoke(stage: str, completed: int, total: int) -> None:
        if stage == "Preparing archive":
            GPSTrackUserPermission.objects.filter(user=user).update(is_active=False)
            GPSTrack.objects.filter(pk=track.id).update(is_active=False)
            LandmarkCollectionUserPermission.objects.filter(user=user).update(
                is_active=False
            )
            LandmarkCollection.objects.filter(pk=collection.id).update(is_active=False)

    result = build_archive(
        user=user, destination=tmp_path / "export.zip", progress=revoke
    )
    assert {r["id"] for r in result.manifest["resources"]} == {
        str(track.id),
        str(collection.id),
    }
    fresh = build_archive(
        user=user, destination=tmp_path / "fresh.zip", progress=_progress
    )
    assert fresh.manifest["selected_resources"] == 0


@pytest.mark.django_db
def test_geo_resource_permissions_exclude_inactive_and_revoked_rows(
    user: User,
    tmp_path: Path,
    write_source: SourceWriter,
) -> None:
    readable = _track(user, write_source)
    inactive = _track(user, write_source)
    GPSTrack.objects.filter(pk=inactive.id).update(is_active=False)
    revoked = _track(user, write_source)
    GPSTrackUserPermission.objects.filter(gps_track=revoked).update(is_active=False)
    GISLayer.objects.create(
        name="Creator alone is not permission",
        created_by=user.email,
        source_f="missing.kml",
        data_f="missing.geojson",
    )
    collection = _collection(user)
    LandmarkCollectionUserPermission.objects.filter(collection=collection).update(
        is_active=False
    )
    result = build_archive(
        user=user, destination=tmp_path / "export.zip", progress=_progress
    )
    assert [resource["id"] for resource in result.manifest["resources"]] == [
        str(readable.id)
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("missing_part", ["source", "processed"])
def test_gis_missing_file_keeps_other_file(
    user: User,
    tmp_path: Path,
    write_source: SourceWriter,
    missing_part: str,
) -> None:
    layer = GISLayer(name="Layer", created_by=user.email)
    layer.source_f = f"{layer.id}/source.kml"
    layer.data_f = f"{layer.id}/processed.geojson"
    if missing_part == "source":
        layer.data_f = write_source(layer.data_f.storage, layer.data_f.name, b"data")
    else:
        layer.source_f = write_source(
            layer.source_f.storage, layer.source_f.name, b"data"
        )
    layer.save()
    GISLayerUserPermission.objects.create(user=user, gis_layer=layer)
    result = build_archive(
        user=user, destination=tmp_path / "export.zip", progress=_progress
    )
    assert result.partial
    assert result.manifest["resources"][0]["outcome"] == "PARTIAL"
    assert result.manifest["resources"][0]["category"] == "layers"
    assert result.manifest["omissions"][0]["category"] == "layers"
    assert result.manifest["omissions"][0]["path"].startswith("layers/")
    with ZipFile(tmp_path / "export.zip") as archive:
        path: str = result.manifest["resources"][0]["files"][0]["path"]
        assert path.startswith("layers/")
        assert archive.read(path) == b"data"


@pytest.mark.django_db
def test_gis_identical_source_is_not_duplicated(
    user: User, tmp_path: Path, write_source: SourceWriter
) -> None:
    layer = GISLayer(name="Layer", created_by=user.email)
    filename: str = write_source(
        layer.source_f.storage, f"{layer.id}/layer.geojson", EMPTY_GEOJSON
    )
    layer.source_f = filename
    layer.data_f = filename
    layer.save()
    GISLayerUserPermission.objects.create(user=user, gis_layer=layer)
    result = build_archive(
        user=user, destination=tmp_path / "export.zip", progress=_progress
    )
    assert result.manifest["resources"][0]["files"][0]["path"].endswith(
        "source.geojson"
    )
    assert len(result.manifest["resources"][0]["files"]) == 1
    assert result.manifest["resources"][0]["category"] == "layers"
    with ZipFile(tmp_path / "export.zip") as archive:
        assert "layers/" in archive.namelist()
        assert not any(name.startswith("gis_layers/") for name in archive.namelist())
        assert archive.read(f"layers/layer--{layer.id}/source.geojson") == EMPTY_GEOJSON


@pytest.mark.django_db
@pytest.mark.parametrize("failure", ["bytes", "positions", "malformed"])
def test_gpx_omissions_retain_exact_geojson(
    user: User,
    tmp_path: Path,
    write_source: SourceWriter,
    settings: Settings,
    failure: str,
) -> None:
    data: bytes = b"invalid JSON" if failure == "malformed" else TRACK_GEOJSON
    _track(user, write_source, data=data)
    if failure == "bytes":
        settings.EXPORT_GPX_MAX_BYTES = 1
    elif failure == "positions":
        settings.EXPORT_GPX_MAX_POSITIONS = 1
    result = build_archive(
        user=user, destination=tmp_path / "export.zip", progress=_progress
    )
    assert result.partial
    with ZipFile(tmp_path / "export.zip") as archive:
        geojson = next(
            name for name in archive.namelist() if name.endswith("track.geojson")
        )
        assert archive.read(geojson) == data
        assert not any(name.endswith(".gpx") for name in archive.namelist())


@pytest.mark.django_db
def test_all_selected_sources_missing_fails(
    user: User, tmp_path: Path, write_source: SourceWriter
) -> None:
    track = _track(user, write_source)
    assert track.file.name is not None
    track.file.storage.delete(track.file.name)
    with pytest.raises(ArchiveBuildError, match="None of the selected"):
        build_archive(
            user=user, destination=tmp_path / "export.zip", progress=_progress
        )


@pytest.mark.django_db
def test_unsafe_and_duplicate_names_have_safe_distinct_paths(
    user: User, tmp_path: Path
) -> None:
    first = _collection(user, name="../../Same <script>\\name")
    second = _collection(user, name=first.name)
    result = build_archive(
        user=user, destination=tmp_path / "export.zip", progress=_progress
    )
    paths: list[str] = [r["files"][0]["path"] for r in result.manifest["resources"]]
    assert len(set(paths)) == len(paths)
    assert all(
        ".." not in path and "\\" not in path and "<" not in path for path in paths
    )
    assert any(str(second.id) in path for path in paths)


@pytest.mark.django_db
def test_scratch_capacity_is_checked_before_building(
    user: User, tmp_path: Path, settings: Settings
) -> None:
    settings.EXPORT_MIN_FREE_BYTES = 2**63
    with pytest.raises(ArchiveBuildError, match="disk space"):
        build_archive(
            user=user, destination=tmp_path / "export.zip", progress=_progress
        )


@pytest.mark.django_db
def test_landmark_archive_preserves_all_stored_coordinate_digits(
    user: User, tmp_path: Path
) -> None:
    collection = _collection(user)
    longitude = Decimal("-87.7654321")
    latitude = Decimal("20.1234567")
    Landmark.objects.create(
        name="Precise entrance",
        collection=collection,
        created_by=user.email,
        latitude=latitude,
        longitude=longitude,
    )
    destination: Path = tmp_path / "export.zip"
    result = build_archive(user=user, destination=destination, progress=_progress)
    with ZipFile(destination) as archive:
        path: str = result.manifest["resources"][0]["files"][0]["path"]
        feature_collection = orjson.loads(archive.read(path))
        assert feature_collection["features"][0]["geometry"]["coordinates"] == [
            float(longitude),
            float(latitude),
        ]


def test_git_mirror_restores_historical_commits(
    tmp_path: Path,
    git_repository: tuple[Path, str, str],
) -> None:
    repository, historical, current = git_repository
    destination: Path = tmp_path / "backup"
    mirrored = mirror_project(
        GitSource(str(repository), "credential-must-never-persist"),
        destination,
        heartbeat=lambda: None,
    )
    assert mirrored.refs["refs/tags/historic-tag"] == historical
    assert mirrored.state == "mirrored"
    assert mirrored.checkout_commit == current
    assert not mirrored.used_fallback_head
    assert (
        "credential-must-never-persist" not in (destination / ".git/config").read_text()
    )
    assert "remote" not in (destination / ".git/config").read_text()
    _restore_and_verify(
        destination,
        destination=tmp_path / "working",
        historical=historical,
        current=current,
    )


def test_git_mirror_missing_source_reports_safe_omission(tmp_path: Path) -> None:
    with pytest.raises(
        SourceUnavailableError,
        match="remote Git repository was not found or is inaccessible",
    ):
        mirror_project(
            GitSource(str(tmp_path / "missing"), "secret"),
            tmp_path / "backup.git",
            heartbeat=lambda: None,
        )


@pytest.mark.parametrize("has_recorded_history", [False, True])
def test_empty_remote_cannot_hide_recorded_history(
    tmp_path: Path, *, has_recorded_history: bool
) -> None:
    remote: Path = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "--initial-branch=main", str(remote))
    destination: Path = tmp_path / "backup"
    source = GitSource(str(remote), "", has_recorded_history=has_recorded_history)
    if has_recorded_history:
        with pytest.raises(SourceUnavailableError, match="despite recorded"):
            mirror_project(source, destination, heartbeat=lambda: None)
    else:
        mirrored = mirror_project(source, destination, heartbeat=lambda: None)
        assert mirrored.state == "empty"
        assert mirrored.refs == {}
        assert list(destination.iterdir()) == []
    assert _git(remote, "for-each-ref") == ""


@pytest.mark.parametrize("tags_only", [False, True])
def test_git_checkout_uses_deterministic_fallback_when_remote_head_is_missing(
    tmp_path: Path,
    git_repository: tuple[Path, str, str],
    *,
    tags_only: bool,
) -> None:
    repository, historical, current = git_repository
    remote: Path = tmp_path / "remote.git"
    _git(tmp_path, "clone", "--mirror", str(repository), str(remote))
    _git(remote, "symbolic-ref", "HEAD", "refs/heads/missing")
    if tags_only:
        _git(remote, "update-ref", "-d", "refs/heads/main")
        _git(remote, "update-ref", "-d", "refs/heads/survey-branch")
    original_refs: str = _git(remote, "show-ref")
    destination: Path = tmp_path / "backup"
    mirrored = mirror_project(
        GitSource(str(remote), ""), destination, heartbeat=lambda: None
    )
    expected: str = historical if tags_only else current
    assert mirrored.state == "mirrored"
    assert mirrored.used_fallback_head
    assert mirrored.checkout_commit == expected
    assert _git(destination, "rev-parse", "HEAD") == expected
    assert _git(destination, "show-ref") == original_refs
    assert _git(destination, "status", "--porcelain") == ""
    assert (destination / "survey.txt").read_text() == (
        "historic data" if tags_only else "current data"
    )


def test_project_with_empty_committed_tree_retains_git_history(tmp_path: Path) -> None:
    remote: Path = tmp_path / "remote"
    remote.mkdir()
    _git(remote, "init", "--initial-branch=main")
    _git(remote, "commit", "--allow-empty", "-m", "Empty initial tree")
    commit: str = _git(remote, "rev-parse", "HEAD")
    destination: Path = tmp_path / "backup"
    mirrored = mirror_project(
        GitSource(str(remote), ""), destination, heartbeat=lambda: None
    )
    assert mirrored.state == "mirrored"
    assert mirrored.checkout_commit == commit
    assert (destination / ".git").is_dir()
    assert not (destination / "PROJECT IS EMPTY").exists()
    assert _git(destination, "rev-list", "--all", "--count") == "1"
    assert _git(destination, "status", "--porcelain") == ""


def test_tracked_symlinks_never_read_external_files_into_checkout_or_zip(
    tmp_path: Path,
    git_repository: tuple[Path, str, str],
) -> None:
    repository, _, _ = git_repository
    private: Path = tmp_path / "private"
    private.mkdir()
    (private / "secret").write_bytes(b"private contents must not enter export")
    (repository / "outside-file").symlink_to(private / "secret")
    (repository / "outside-directory").symlink_to(private, target_is_directory=True)
    _git(repository, "add", "outside-file", "outside-directory")
    _git(repository, "commit", "-m", "External symlink references")
    destination: Path = tmp_path / "backup"
    mirror_project(GitSource(str(repository), ""), destination, heartbeat=lambda: None)
    archive_path: Path = tmp_path / "symlinks.zip"
    with ZipFile(archive_path, "w") as archive:
        for name in ("outside-file", "outside-directory"):
            path: Path = destination / name
            assert path.is_file()
            assert not path.is_symlink()
            assert _git(destination, "ls-files", "--stage", name).startswith("120000 ")
            _write_file(archive, path, name)
    with ZipFile(archive_path) as archive:
        assert archive.read("outside-file") == str(private / "secret").encode()
        assert archive.read("outside-directory") == str(private).encode()
        assert all(
            b"private contents" not in archive.read(name) for name in archive.namelist()
        )
    assert _git(destination, "status", "--porcelain") == ""


def _project_without_history(user: User) -> Project:
    project: Project = ProjectFactory.create(created_by=user.email)
    UserProjectPermissionFactory.create(
        target=user, project=project, level=PermissionLevel.READ_ONLY
    )
    assert not project.commits.exists()
    assert not project.git_repo_dir.exists()
    return project


def _assert_remote_absent(client: gitlab.Gitlab, project: Project) -> None:
    with pytest.raises(gitlab.exceptions.GitlabGetError) as caught:
        client.projects.get(f"{django_settings.GITLAB_GROUP_NAME}/{project.id}")
    assert caught.value.response_code == HTTPStatus.NOT_FOUND


def _assert_empty_project_export(
    user: User, project: Project, destination: Path, *, state: str
) -> None:
    result = build_archive(user=user, destination=destination, progress=_progress)
    assert not result.partial
    record = result.manifest["resources"][0]
    assert record["id"] == str(project.id)
    assert record["outcome"] == "OK"
    assert record["repository_state"] == state
    assert record["refs"] == {}
    assert any(
        note["category"] == "projects" and note["id"] == str(project.id)
        for note in result.manifest["notes"]
    )
    with ZipFile(destination) as archive:
        project_files: list[str] = [
            name
            for name in archive.namelist()
            if name.startswith("projects/") and not name.endswith("/")
        ]
        assert len(project_files) == 1
        assert project_files[0].endswith("/PROJECT IS EMPTY")
        assert archive.read(project_files[0]) == b""
        assert len(record["files"]) == 1
        assert record["files"][0]["path"] == project_files[0]
        assert record["files"][0]["size_bytes"] == 0
        archive.extractall(destination.parent / "restored")
    marker = next(
        (destination.parent / "restored" / "projects").glob("*/PROJECT IS EMPTY")
    )
    assert list(marker.parent.iterdir()) == [marker]
    assert not project.commits.exists()
    assert not project.git_repo_dir.exists()


@pytest.mark.django_db
@pytest.mark.skip_if_lighttest
def test_uninitialized_project_exports_empty_marker_without_creating_remote(
    user: User, tmp_path: Path, gitlab_client: gitlab.Gitlab
) -> None:
    project = _project_without_history(user)
    _assert_remote_absent(gitlab_client, project)
    _assert_empty_project_export(
        user, project, tmp_path / "export.zip", state="uninitialized"
    )
    _assert_remote_absent(gitlab_client, project)


@pytest.mark.django_db
@pytest.mark.skip_if_lighttest
def test_missing_remote_with_recorded_history_remains_an_omission(
    user: User, tmp_path: Path, gitlab_client: gitlab.Gitlab
) -> None:
    project = _project_without_history(user)
    ProjectCommitFactory.create(project=project)
    _collection(user)
    _assert_remote_absent(gitlab_client, project)
    result = build_archive(
        user=user, destination=tmp_path / "export.zip", progress=_progress
    )
    assert result.partial
    assert result.manifest["omissions"][0]["id"] == str(project.id)
    assert result.manifest["resources"][0]["outcome"] == "OMITTED"
    assert project.commits.count() == 1
    assert not project.git_repo_dir.exists()
    _assert_remote_absent(gitlab_client, project)


@pytest.mark.django_db
@pytest.mark.skip_if_lighttest
def test_remote_history_is_cloned_even_when_database_has_no_recorded_commits(
    user: User, tmp_path: Path, gitlab_project: tuple[Project, str, str]
) -> None:
    project, historical, current = gitlab_project
    assert not project.commits.exists()
    assert not project.git_repo_dir.exists()
    destination: Path = tmp_path / "export.zip"
    result = build_archive(user=user, destination=destination, progress=_progress)
    assert not result.partial
    assert result.manifest["resources"][0]["repository_state"] == "mirrored"
    with ZipFile(destination) as archive:
        archive.extractall(tmp_path / "restored")
    repository = next((tmp_path / "restored" / "projects").glob("*/.git")).parent
    _restore_and_verify(
        repository,
        destination=tmp_path / "working",
        historical=historical,
        current=current,
    )
    assert not project.commits.exists()
    assert not project.git_repo_dir.exists()


@pytest.mark.django_db
@pytest.mark.skip_if_lighttest
@pytest.mark.parametrize(
    "failure", ["group_missing", "group_mismatch", "invalid_token"]
)
def test_unverified_gitlab_access_cannot_become_an_empty_export(
    user: User, tmp_path: Path, settings: Settings, failure: str
) -> None:
    project = _project_without_history(user)
    if failure == "group_missing":
        settings.GITLAB_GROUP_ID = "0"
    elif failure == "group_mismatch":
        settings.GITLAB_GROUP_NAME = f"nonexistent-{project.id}"
    else:
        settings.GITLAB_TOKEN = f"invalid-{project.id}"
    with pytest.raises(ArchiveBuildError):
        build_archive(
            user=user, destination=tmp_path / "export.zip", progress=_progress
        )
    assert not project.commits.exists()
    assert not project.git_repo_dir.exists()


@pytest.mark.django_db
@pytest.mark.skip_if_lighttest
def test_empty_archive_and_initial_commit_lifecycle(
    user: User, tmp_path: Path, gitlab_client: gitlab.Gitlab
) -> None:
    """All genuinely empty states precede the first commit in one allocation."""

    class CleanupBoundaryError(Exception):
        """Stop the lifecycle without passing a remote object to its cleanup."""

    project: Project = _project_without_history(user)
    remote: GitlabProject | None = None

    def exercise_lifecycle() -> None:
        nonlocal remote
        with cleanup_remote_on_exit(
            gitlab_client, f"{django_settings.GITLAB_GROUP_NAME}/{project.id}"
        ):
            with creation_allocation(
                "empty-archive", django_settings.GITLAB_GROUP_ID, str(project.id)
            ):
                remote = gitlab_client.projects.create(
                    {
                        "name": str(project.id),
                        "namespace_id": django_settings.GITLAB_GROUP_ID,
                        "merge_requests_access_level": "disabled",
                        "builds_access_level": "disabled",
                    }
                )
            for access in ("enabled", "private"):
                remote.repository_access_level = access
                remote.save()
                directory: Path = tmp_path / access
                directory.mkdir()
                assert remote.empty_repo is True
                _assert_empty_project_export(
                    user, project, directory / "export.zip", state="empty"
                )
                remote.refresh()
                assert remote.empty_repo is True
                assert remote.branches.list(get_all=True) == []

            ProjectCommitFactory.create(project=project)
            _collection(user)
            destination: Path = tmp_path / "recorded-history.zip"
            result = build_archive(
                user=user, destination=destination, progress=_progress
            )
            assert result.partial
            assert result.manifest["omissions"] == [
                {
                    "category": "projects",
                    "id": str(project.id),
                    "name": project.name,
                    "reason": (
                        "The Git repository is empty despite recorded project history."
                    ),
                }
            ]
            assert result.manifest["resources"][0]["outcome"] == "OMITTED"
            assert result.manifest["resources"][1]["outcome"] == "OK"
            with ZipFile(destination) as archive:
                assert not any(
                    name.startswith("projects/") and name != "projects/"
                    for name in archive.namelist()
                )
                assert any(
                    name.startswith("landmarks/") and name.endswith(".geojson")
                    for name in archive.namelist()
                )
            assert project.commits.count() == 1
            assert not project.git_repo_dir.exists()
            remote.refresh()
            assert remote.empty_repo is True
            assert remote.branches.list(get_all=True) == []
            project.commits.all().delete()

            remote.repository_access_level = "disabled"
            remote.save()
            with pytest.raises(ArchiveBuildError):
                build_archive(
                    user=user, destination=tmp_path / "disabled.zip", progress=_progress
                )
            assert not project.commits.exists()
            assert not project.git_repo_dir.exists()
            remote.repository_access_level = "enabled"
            remote.save()
            assert_initial_commit_lifecycle(
                remote,
                gitlab_client,
                create_initial_commit=_create_initial_gitlab_commit,
                max_attempts=INITIAL_COMMIT_ATTEMPTS,
            )
            raise CleanupBoundaryError

    with pytest.raises(CleanupBoundaryError):
        exercise_lifecycle()
    assert remote is not None
    assert_remote_deleted(gitlab_client, int(remote.id))


def test_s3_download_preserves_complete_multichunk_source(
    tmp_path: Path, write_source: SourceWriter
) -> None:
    track = GPSTrack()
    contents: bytes = b"a" * (1024 * 1024 + 17)
    track.file = write_source(track.file.storage, f"{track.id}.geojson", contents)
    destination: Path = tmp_path / "source"
    download_source(track.file, destination)
    assert destination.read_bytes() == contents


def test_s3_missing_source_is_an_omission(tmp_path: Path) -> None:
    track = GPSTrack()
    track.file = f"{track.id}.geojson"
    with pytest.raises(SourceUnavailableError, match="file is missing"):
        download_source(track.file, tmp_path / "source")
