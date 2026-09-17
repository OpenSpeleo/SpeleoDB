"""Build permission-scoped, restorable archives without shared mutable state."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import Any
from zipfile import ZIP_DEFLATED
from zipfile import ZIP_STORED
from zipfile import ZipFile

import orjson
from django.db.models import OuterRef
from django.db.models import Q
from django.db.models import Subquery
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.text import slugify

from speleodb.api.v2.gis_geometry_access import accessible_gis_geometries_queryset
from speleodb.api.v2.gis_layer_access import accessible_gis_layers_queryset
from speleodb.api.v2.gps_track_access import accessible_gps_tracks_queryset
from speleodb.api.v2.landmark_access import accessible_landmark_collections_queryset
from speleodb.background_jobs.archive_sources import ArchiveBuildError
from speleodb.background_jobs.archive_sources import SourceUnavailableError
from speleodb.background_jobs.archive_sources import check_scratch_space
from speleodb.background_jobs.archive_sources import derive_gpx
from speleodb.background_jobs.archive_sources import download_source
from speleodb.background_jobs.archive_sources import file_sha256
from speleodb.background_jobs.archive_sources import mirror_project
from speleodb.background_jobs.archive_sources import project_git_source
from speleodb.common.enums import PermissionLevel
from speleodb.gis.landmark_geojson import landmark_geojson_feature
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISLayer
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from django.db.models.fields.files import FieldFile

    from speleodb.users.models import User


ARCHIVE_DIRECTORIES: tuple[str, ...] = (
    "projects/",
    "geojsons/",
    "geometries/",
    "layers/",
    "gps tracks/",
    "landmarks/",
)
SLUG_LENGTH: int = 80
LANDMARK_COORDINATE_PRECISION: int = 7
COMPRESSED_SUFFIXES: frozenset[str] = frozenset(
    {".pack", ".zip", ".kmz", ".gz", ".jpg", ".jpeg", ".png"}
)
README: str = """# SpeleoDB export

This archive contains the six supported categories accessible with READ_ONLY
permission or higher when generation began. Project WEB_VIEWER access is excluded.
Each resource is captured separately; this is not an atomic database/Git snapshot.
See manifest.json for exact source revisions, checksums, timestamps, and omissions.

## Contents

- projects/: readable project files beside a complete .git directory, including
  advertised branches, tags, and their reachable commit history. Open the files
  directly or run Git commands from projects/<name>--<uuid>/.
  Server reflogs, unreachable objects, uncommitted files, external Git LFS objects,
  and external submodule repositories are not included.
  Tracked symlinks are stored as regular files containing their target paths;
  Git retains their original symlink objects without following external targets.
  Zero-commit projects contain only the zero-byte file PROJECT IS EMPTY. Empty
  and uninitialized states are informational notes in manifest.json.
- geojsons/: each project's latest stored GeoJSON. It may predate the Git HEAD.
- geometries/: each geometry's stored LineString or Polygon GeoJSON.
  Coordinates are preserved; revision, name, color, and creator are in manifest.json.
- layers/: original stored uploads plus distinct processed GeoJSON files.
- gps tracks/: exact stored GeoJSON plus derived GPX 1.1 when conversion succeeds.
  Imported GPX timestamps and original GPX files are not retained by SpeleoDB.
- landmarks/: one GeoJSON per accessible collection, including empty collections.

This is not a full account/database restore. Station attachments, experiments,
sensor data, cylinders, and other database-only categories are not included.

## Partial exports

The manifest's omissions array explains missing files and unsuccessful derived
GPX conversions. A PARTIAL export still contains the other completed resources.
Empty optional project GeoJSON history is recorded as a note, not a failure.
Archive download availability ends 24 hours after the archive becomes ready.
"""


@dataclass(frozen=True)
class ArchiveResult:
    manifest: dict[str, Any]
    size_bytes: int
    sha256: str
    partial: bool


@dataclass(frozen=True)
class ArchiveSource:
    category: str
    resource: (
        Project
        | ProjectGeoJSON
        | GISGeometry
        | GISLayer
        | GPSTrack
        | LandmarkCollection
    )
    name: str
    resource_id: str
    has_recorded_history: bool = True

    @property
    def stem(self) -> str:
        return f"{slugify(self.name)[:SLUG_LENGTH] or 'untitled'}--{self.resource_id}"


@dataclass
class StagedResource:
    files: list[tuple[Path, str]] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    omissions: list[dict[str, str]] = field(default_factory=list)
    notes: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _snapshot_sources(user: User) -> tuple[list[ArchiveSource], list[dict[str, str]]]:
    direct, teams = user.fetch_all_project_permissions()
    projects: list[Project] = list(
        Project.objects.filter(is_active=True)
        .filter(
            Q(
                pk__in=direct.filter(level__gte=PermissionLevel.READ_ONLY).values(
                    "project_id"
                )
            )
            | Q(
                pk__in=teams.filter(level__gte=PermissionLevel.READ_ONLY).values(
                    "project_id"
                )
            )
        )
        .order_by("id")
    )
    recorded_project_ids: set[UUID] = set(
        ProjectCommit.objects.filter(
            project_id__in=[project.id for project in projects]
        )
        .values_list("project_id", flat=True)
        .distinct()
    )
    sources: list[ArchiveSource] = [
        ArchiveSource(
            "projects",
            project,
            project.name,
            str(project.id),
            has_recorded_history=project.id in recorded_project_ids,
        )
        for project in projects
    ]
    latest = (
        ProjectGeoJSON.objects.filter(project_id=OuterRef("pk"))
        .order_by("-commit__authored_date", "-creation_date", "commit_id")
        .values("pk")[:1]
    )
    latest_ids = (
        Project.objects.filter(pk__in=[project.id for project in projects])
        .annotate(export_geojson_id=Subquery(latest))
        .values("export_geojson_id")
    )
    geojsons: list[ProjectGeoJSON] = list(
        ProjectGeoJSON.objects.filter(pk__in=Subquery(latest_ids))
        .select_related("project", "commit")
        .order_by("project_id")
    )
    sources.extend(
        ArchiveSource(
            "geojsons", geojson, geojson.project.name, str(geojson.project_id)
        )
        for geojson in geojsons
    )
    available_geojson_ids: set[str] = {str(g.project_id) for g in geojsons}
    notes: list[dict[str, str]] = [
        {
            "category": "geojsons",
            "id": str(project.id),
            "name": project.name,
            "reason": "No stored GeoJSON version exists for this project.",
        }
        for project in projects
        if str(project.id) not in available_geojson_ids
    ]
    sources.extend(
        ArchiveSource("geometries", geometry, geometry.name, str(geometry.id))
        for geometry in accessible_gis_geometries_queryset(user).order_by("id")
    )
    sources.extend(
        ArchiveSource("layers", layer, layer.name, str(layer.id))
        for layer in accessible_gis_layers_queryset(user).order_by("id")
    )
    sources.extend(
        ArchiveSource("gps tracks", track, track.name, str(track.id))
        for track in accessible_gps_tracks_queryset(user).order_by("id")
    )
    sources.extend(
        ArchiveSource("landmarks", collection, collection.name, str(collection.id))
        for collection in accessible_landmark_collections_queryset(
            user, ensure_personal=False
        ).order_by("id")
    )
    # Querysets are deliberately evaluated before progress callbacks or network
    # reads. The selected records/FieldFile names survive permission revocation.
    return sources, notes


def _stage_file(
    field_file: FieldFile,
    *,
    directory: Path,
    filename: str,
    archive_path: str,
    staged: StagedResource,
) -> Path | None:
    destination: Path = directory / filename
    try:
        download_source(field_file, destination)
    except SourceUnavailableError as error:
        staged.omissions.append({"path": archive_path, "reason": str(error)})
        return None
    staged.files.append((destination, archive_path))
    return destination


def _stage_landmarks(collection: LandmarkCollection, destination: Path) -> None:
    metadata: dict[str, Any] = {
        "type": "FeatureCollection",
        "id": str(collection.id),
        "name": collection.name,
        "description": collection.description,
        "color": collection.color,
        "collection_type": collection.collection_type,
        "created_by": collection.created_by,
        "creation_date": collection.creation_date.isoformat(),
        "modified_date": collection.modified_date.isoformat(),
    }
    # Deliberately query by the snapshotted collection ID, without checking its
    # current permission/activity again. Do not load all features into a list.
    landmarks = Landmark.objects.filter(collection_id=collection.id).order_by(
        Lower("name"), "id"
    )
    with destination.open("wb") as output:
        output.write(orjson.dumps(metadata)[:-1] + b',"features":[')
        separator: bytes = b""
        for landmark in landmarks.iterator(chunk_size=500):
            landmark.collection = collection
            feature: dict[str, Any] = landmark_geojson_feature(
                landmark,
                coordinate_precision=LANDMARK_COORDINATE_PRECISION,
            )
            feature["properties"]["modified_date"] = landmark.modified_date.isoformat()
            encoded: bytes = orjson.dumps(feature)
            check_scratch_space(destination.parent, required_bytes=len(encoded))
            output.write(separator + encoded)
            separator = b","
        output.write(b"]}")


def _stage_resource(
    source: ArchiveSource,
    directory: Path,
    *,
    heartbeat: Callable[[], None],
) -> StagedResource:
    resource = source.resource
    staged = StagedResource()
    staged.metadata.update(
        creation_date=resource.creation_date.isoformat(),
        modified_date=resource.modified_date.isoformat(),
    )
    if not isinstance(resource, ProjectGeoJSON):
        staged.metadata.update(created_by=resource.created_by, color=resource.color)
    prefix: str = f"{source.category}/{source.stem}"
    if isinstance(resource, Project):
        repository: Path = directory / "project"
        mirrored = mirror_project(
            project_git_source(
                resource.id, has_recorded_history=source.has_recorded_history
            ),
            repository,
            heartbeat=heartbeat,
        )
        staged.metadata.update(
            refs=mirrored.refs,
            repository_state=mirrored.state,
            checkout_commit=mirrored.checkout_commit,
            description=resource.description,
            project_type=resource.type,
            country=str(resource.country),
        )
        if mirrored.state != "mirrored":
            staged.notes.append(
                {
                    "reason": (
                        "Git storage has not been initialized for this project; "
                        "included the PROJECT IS EMPTY marker."
                        if mirrored.state == "uninitialized"
                        else "The Git repository is empty; included the "
                        "PROJECT IS EMPTY marker."
                    )
                }
            )
            (repository / "PROJECT IS EMPTY").touch()
        if mirrored.used_fallback_head:
            staged.notes.append(
                {
                    "reason": "The remote HEAD was unavailable; checked out the "
                    f"recorded fallback commit {mirrored.checkout_commit}."
                }
            )
        for path in sorted(repository.rglob("*")):
            if path.is_symlink():
                raise ArchiveBuildError("The Git mirror contains an unsafe symlink.")
            if path.is_dir():
                staged.directories.append(f"{prefix}/{path.relative_to(repository)}/")
            elif path.is_file():
                staged.files.append((path, f"{prefix}/{path.relative_to(repository)}"))
    elif isinstance(resource, ProjectGeoJSON):
        staged.metadata.update(
            commit_sha=resource.commit_id,
            commit_authored_date=resource.commit.authored_date.isoformat(),
        )
        _stage_file(
            resource.file,
            directory=directory,
            filename="data.geojson",
            archive_path=f"{prefix}.geojson",
            staged=staged,
        )
    elif isinstance(resource, GISGeometry):
        geometry_path: Path = directory / "geometry.geojson"
        geometry_path.write_bytes(orjson.dumps(resource.geojson))
        staged.files.append((geometry_path, f"{prefix}.geojson"))
        staged.metadata["revision"] = resource.revision
    elif isinstance(resource, GISLayer):
        suffix: str = Path(resource.source_f.name or "").suffix.lower()
        safe_suffix: str = (
            suffix
            if suffix in {".geojson", ".json", ".kml", ".kmz", ".zip", ".topojson"}
            else ".bin"
        )
        _stage_file(
            resource.source_f,
            directory=directory,
            filename=f"source{safe_suffix}",
            archive_path=f"{prefix}/source{safe_suffix}",
            staged=staged,
        )
        if resource.data_f.name != resource.source_f.name:
            _stage_file(
                resource.data_f,
                directory=directory,
                filename="processed.geojson",
                archive_path=f"{prefix}/processed.geojson",
                staged=staged,
            )
        staged.metadata["description"] = resource.description
    elif isinstance(resource, GPSTrack):
        geojson: Path | None = _stage_file(
            resource.file,
            directory=directory,
            filename="track.geojson",
            archive_path=f"{prefix}/track.geojson",
            staged=staged,
        )
        if geojson is not None:
            gpx_path: str = f"{prefix}/track.gpx"
            try:
                gpx: Path = directory / "track.gpx"
                derive_gpx(geojson, gpx, name=resource.name)
                staged.files.append((gpx, gpx_path))
            except SourceUnavailableError as error:
                staged.omissions.append({"path": gpx_path, "reason": str(error)})
    elif isinstance(resource, LandmarkCollection):
        destination: Path = directory / "collection.geojson"
        _stage_landmarks(resource, destination)
        staged.files.append((destination, f"{prefix}.geojson"))
    return staged


def _write_file(archive: ZipFile, source: Path, archive_path: str) -> dict[str, Any]:
    size: int = source.stat().st_size
    check_scratch_space(source.parent, required_bytes=size)
    # Everything is fully staged before opening a ZIP entry. Exceptions during
    # writing are fatal: skipping would leave an apparently valid truncated file.
    archive.write(
        source,
        arcname=archive_path,
        compress_type=ZIP_STORED
        if source.suffix in COMPRESSED_SUFFIXES
        else ZIP_DEFLATED,
    )
    return {"path": archive_path, "size_bytes": size, "sha256": file_sha256(source)}


def build_archive(
    *,
    user: User,
    destination: Path,
    progress: Callable[[str, int, int], None],
) -> ArchiveResult:
    """Build one ZIP from a fresh permission snapshot and return safe metadata."""
    captured_at: str = timezone.now().isoformat()
    sources, notes = _snapshot_sources(user)
    total: int = len(sources)
    manifest: dict[str, Any] = {
        "format_version": 2,
        "permission_snapshot_at": captured_at,
        "capture_policy": (
            "Permissions at generation start; sources captured separately."
        ),
        "resources": [],
        "omissions": [],
        "notes": notes,
        "selected_resources": total,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    check_scratch_space(destination.parent)
    progress("Preparing archive", 0, total)
    successful_resources: int = 0
    with ZipFile(
        destination, "w", compression=ZIP_DEFLATED, allowZip64=True
    ) as archive:
        for directory in ARCHIVE_DIRECTORIES:
            archive.writestr(directory, b"")
        for index, source in enumerate(sources):
            stage: str = f"Exporting {source.category}"
            progress(stage, index, total)
            record: dict[str, Any] = {
                "category": source.category,
                "id": source.resource_id,
                "name": source.name,
                "capture_started_at": timezone.now().isoformat(),
                "files": [],
            }
            with TemporaryDirectory(
                prefix="export-source-", dir=destination.parent
            ) as tmp:
                try:
                    staged = _stage_resource(
                        source,
                        Path(tmp),
                        heartbeat=partial(progress, stage, index, total),
                    )
                except SourceUnavailableError as error:
                    staged = StagedResource(omissions=[{"reason": str(error)}])
                record.update(staged.metadata)
                for directory in staged.directories:
                    archive.writestr(directory, b"")
                for path, archive_path in staged.files:
                    record["files"].append(_write_file(archive, path, archive_path))
                    progress(stage, index, total)
                for omission in staged.omissions:
                    manifest["omissions"].append(
                        {
                            "category": source.category,
                            "id": source.resource_id,
                            "name": source.name,
                            **omission,
                        }
                    )
                for note in staged.notes:
                    manifest["notes"].append(
                        {
                            "category": source.category,
                            "id": source.resource_id,
                            "name": source.name,
                            **note,
                        }
                    )
                if staged.files:
                    successful_resources += 1
                record["outcome"] = (
                    "OMITTED"
                    if not staged.files
                    else "PARTIAL"
                    if staged.omissions
                    else "OK"
                )
            record["capture_completed_at"] = timezone.now().isoformat()
            manifest["resources"].append(record)
            progress(stage, index + 1, total)
        if total and not successful_resources:
            raise ArchiveBuildError("None of the selected sources could be exported.")
        manifest["completed_at"] = timezone.now().isoformat()
        manifest["exported_resources"] = successful_resources
        manifest["status"] = "PARTIAL" if manifest["omissions"] else "READY"
        progress("Finalizing archive", total, total)
        archive.writestr("README.md", README)
        archive.writestr(
            "manifest.json", orjson.dumps(manifest, option=orjson.OPT_INDENT_2)
        )
    return ArchiveResult(
        manifest=manifest,
        size_bytes=destination.stat().st_size,
        sha256=file_sha256(destination),
        partial=bool(manifest["omissions"]),
    )
