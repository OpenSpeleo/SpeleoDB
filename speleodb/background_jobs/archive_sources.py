"""Read-only, disk-backed export source operations.

Nothing in this module initializes remote projects or uses shared Git checkouts.
Only source-specific missing/corrupt data is safe to omit; infrastructure errors
must reach the job retry machinery.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
from tempfile import TemporaryFile
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal
from typing import Protocol
from urllib.parse import quote

import gitlab.exceptions
import orjson
from botocore.exceptions import BotoCoreError
from botocore.exceptions import ClientError
from django.conf import settings
from storages.backends.s3 import S3Storage
from storages.utils import clean_name

from speleodb.background_jobs.git_supervisor import TERMINATE_SECONDS
from speleodb.background_jobs.git_supervisor import TIMEOUT_EXIT_CODE
from speleodb.git_engine.client import GitlabClient
from speleodb.utils.gpx import GPX_VERSION
from speleodb.utils.gpx import InvalidGPSTrackGeoJSONError
from speleodb.utils.gpx import gps_track_geojson_to_gpx

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from django.db.models.fields.files import FieldFile


CHUNK_BYTES: int = 1024 * 1024
MIN_FREE_BYTES: int = 64 * 1024 * 1024
SOURCE_READ_ATTEMPTS: int = 3
GIT_TIMEOUT_SECONDS: int = 600
GIT_POLL_SECONDS: float = 1.0
MAX_GIT_ERROR_BYTES: int = 64 * 1024
MAX_GPX_INPUT_BYTES: int = 16 * 1024 * 1024
MAX_GPX_POSITIONS: int = 250_000
S3_MISSING_CODES: frozenset[str] = frozenset({"404", "NoSuchKey", "NotFound"})
S3_AUTH_CODES: frozenset[str] = frozenset(
    {"403", "AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"}
)


class ArchiveBuildError(Exception):
    """Safe, credential-free explanation of a fatal export failure."""


class SourceUnavailableError(Exception):
    """One missing/corrupt source can be reported in a partial export."""


class GitCloneUnavailableError(SourceUnavailableError):
    """A clone cannot find/read its remote; other Git failures are not empty data."""


type GitRepositoryState = Literal["mirrored", "empty", "uninitialized"]


@dataclass(frozen=True)
class GitSource:
    url: str
    token: str
    project_id: UUID | None = None
    has_recorded_history: bool = True


@dataclass(frozen=True)
class GitMirrorResult:
    refs: dict[str, str]
    state: GitRepositoryState
    checkout_commit: str | None = None
    used_fallback_head: bool = False


class _ByteReader(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


def check_scratch_space(directory: Path, *, required_bytes: int = 0) -> None:
    reserve: int = int(getattr(settings, "EXPORT_MIN_FREE_BYTES", MIN_FREE_BYTES))
    if shutil.disk_usage(directory).free < reserve + required_bytes:
        raise ArchiveBuildError(
            "Insufficient temporary disk space to build the export."
        )


def file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _copy_stream(source: _ByteReader, destination: Path) -> None:
    with destination.open("wb") as output:
        while chunk := source.read(CHUNK_BYTES):
            check_scratch_space(destination.parent, required_bytes=len(chunk))
            output.write(chunk)


def _download_once(field: FieldFile, destination: Path) -> None:
    storage = field.storage
    name: str | None = field.name
    if not name:
        raise SourceUnavailableError("The selected source has no stored file.")
    if isinstance(storage, S3Storage):
        # S3File.open() spools the object, potentially entirely into RAM. Read
        # the botocore StreamingBody directly into our explicit disk file.
        key: str = storage._normalize_name(clean_name(name))  # type: ignore[no-untyped-call]  # noqa: SLF001
        response: dict[str, Any] = storage.connection.meta.client.get_object(
            Bucket=storage.bucket.name,
            Key=key,
        )
        with contextlib.closing(response["Body"]) as body:
            check_scratch_space(
                destination.parent, required_bytes=int(response.get("ContentLength", 0))
            )
            _copy_stream(body, destination)
        return
    with storage.open(name, "rb") as source:
        _copy_stream(source, destination)


def download_source(field: FieldFile, destination: Path) -> None:
    """Download a selected source with bounded memory and safe error reporting."""
    if not field.name:
        raise SourceUnavailableError("The selected source has no stored file.")
    for attempt in range(SOURCE_READ_ATTEMPTS):
        # A failed streaming read can leave a large partial file. Remove it
        # before checking capacity for the next complete download.
        destination.unlink(missing_ok=True)
        try:
            _download_once(field, destination)
            return
        except FileNotFoundError:
            raise SourceUnavailableError(
                "The selected source file is missing."
            ) from None
        except ClientError as error:
            code: str = str(error.response.get("Error", {}).get("Code", ""))
            if code in S3_MISSING_CODES:
                raise SourceUnavailableError(
                    "The selected source file is missing."
                ) from None
            if code in S3_AUTH_CODES:
                raise ArchiveBuildError(
                    "Source storage authorization failed."
                ) from None
            if attempt == SOURCE_READ_ATTEMPTS - 1:
                raise ArchiveBuildError("Source storage is unavailable.") from None
        except BotoCoreError:
            if attempt == SOURCE_READ_ATTEMPTS - 1:
                raise ArchiveBuildError("Source storage is unavailable.") from None
        time.sleep(attempt + 1)


def project_git_source(
    project_id: UUID, *, has_recorded_history: bool = True
) -> GitSource:
    """Use configuration directly, without initializing GitlabManager."""
    protocol: str = str(settings.GITLAB_HTTP_PROTOCOL)
    host: str = str(settings.GITLAB_HOST_URL)
    group: str = str(settings.GITLAB_GROUP_NAME)
    if protocol not in {"https", "http"} or any(c in host for c in "@/?#"):
        raise ArchiveBuildError("The Git server configuration is invalid.")
    return GitSource(
        url=f"{protocol}://{host}/{quote(group, safe='/')}/{project_id}.git",
        token=str(settings.GITLAB_TOKEN),
        project_id=project_id,
        has_recorded_history=has_recorded_history,
    )


def _stop_supervisor(process: subprocess.Popen[bytes]) -> None:
    # Closing our liveness pipe requests group cleanup even if a Python soft
    # limit interrupts the caller. Leave time for TERM followed by group KILL.
    try:
        process.wait(timeout=TERMINATE_SECONDS + 2 * GIT_POLL_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _run_git(
    arguments: list[str],
    *,
    directory: Path,
    environment: dict[str, str],
    heartbeat: Callable[[], None],
    expected_exit_codes: tuple[int, ...] = (0,),
) -> bytes:
    executable: str | None = shutil.which("git")
    if executable is None:
        raise ArchiveBuildError("Git is not installed on the export worker.")
    deadline: float = time.monotonic() + GIT_TIMEOUT_SECONDS
    parent_read: int
    parent_write: int
    parent_read, parent_write = os.pipe()
    with (
        os.fdopen(parent_read, "rb") as liveness_reader,
        os.fdopen(parent_write, "wb") as liveness_writer,
        TemporaryFile() as errors,
        subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                str(Path(__file__).with_name("git_supervisor.py")),
                "--parent-fd",
                str(parent_read),
                "--timeout",
                str(GIT_TIMEOUT_SECONDS),
                "--",
                executable,
                "-c",
                "credential.helper=",
                *arguments,
            ],
            cwd=directory,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=errors,
            start_new_session=True,
            pass_fds=(parent_read,),
        ) as process,
    ):
        liveness_reader.close()
        try:
            while True:
                check_scratch_space(directory)
                heartbeat()
                if time.monotonic() >= deadline:
                    raise ArchiveBuildError("The Git source timed out.")
                try:
                    output, _ = process.communicate(timeout=GIT_POLL_SECONDS)
                    break
                except subprocess.TimeoutExpired:
                    continue
        finally:
            liveness_writer.close()
            _stop_supervisor(process)
        if process.returncode not in expected_exit_codes:
            if process.returncode == TIMEOUT_EXIT_CODE:
                raise ArchiveBuildError("The Git source timed out.")
            errors.seek(0)
            detail: bytes = errors.read(MAX_GIT_ERROR_BYTES).lower()
            if arguments[0] == "fsck":
                raise SourceUnavailableError("The selected Git repository is corrupt.")
            if b"authentication failed" in detail or b"access denied" in detail:
                raise ArchiveBuildError("Git source authorization failed.")
            if b"not found" in detail or b"does not exist" in detail:
                if arguments[0] == "clone":
                    raise GitCloneUnavailableError(
                        "The remote Git repository was not found or is inaccessible."
                    )
                raise SourceUnavailableError(
                    "The remote Git repository was not found or is inaccessible."
                )
            raise ArchiveBuildError("The Git source could not be read or verified.")
        return output


def _empty_project_state(source: GitSource) -> GitRepositoryState | None:
    """Confirm a zero-history project's namespace before representing empty data."""
    client = GitlabClient(
        f"{settings.GITLAB_HTTP_PROTOCOL}://{settings.GITLAB_HOST_URL}",
        private_token=source.token,
        keep_base_url=settings.GITLAB_HTTP_PROTOCOL == "http",
    )
    try:
        group = client.groups.get(str(settings.GITLAB_GROUP_ID))
        if group.full_path != settings.GITLAB_GROUP_NAME:
            raise ArchiveBuildError("The Git namespace configuration is inconsistent.")
        try:
            project = client.projects.get(
                f"{settings.GITLAB_GROUP_NAME}/{source.project_id}"
            )
        except gitlab.exceptions.GitlabGetError as error:
            if error.response_code == HTTPStatus.NOT_FOUND:
                return "uninitialized"
            raise
        if project.attributes.get("empty_repo") is True and project.attributes.get(
            "repository_access_level"
        ) in {"enabled", "private"}:
            return "empty"
        return None
    except gitlab.exceptions.GitlabError:
        raise ArchiveBuildError(
            "Git source access could not be verified for an empty project."
        ) from None
    finally:
        client.session.close()


def mirror_project(
    source: GitSource,
    destination: Path,
    *,
    heartbeat: Callable[[], None],
) -> GitMirrorResult:
    """Restore HEAD beside a complete .git mirror without persisting credentials."""
    destination.mkdir()
    repository: Path = destination / ".git"
    environment: dict[str, str] = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    with TemporaryDirectory(prefix="export-git-auth-", dir=destination.parent) as auth:
        askpass: Path = Path(auth) / "askpass"
        askpass.write_text(
            '#!/bin/sh\ncase "$1" in\n'
            '  *Username*) printf "%s\\n" "oauth2" ;;\n'
            '  *Password*) printf "%s\\n" "$SPELEODB_EXPORT_GIT_TOKEN" ;;\n'
            "  *) exit 1 ;;\nesac\n",
            encoding="utf-8",
        )
        askpass.chmod(0o700)
        environment.update(
            GIT_ASKPASS=str(askpass),
            GIT_TERMINAL_PROMPT="0",
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            SPELEODB_EXPORT_GIT_TOKEN=source.token,
        )
        try:
            _run_git(
                ["clone", "--mirror", "--no-local", "--", source.url, str(repository)],
                directory=destination.parent,
                environment=environment,
                heartbeat=heartbeat,
            )
        except GitCloneUnavailableError:
            if source.has_recorded_history or source.project_id is None:
                raise
            empty_state: GitRepositoryState | None = _empty_project_state(source)
            if empty_state is None:
                raise
            if repository.exists():
                shutil.rmtree(repository)
            return GitMirrorResult(refs={}, state=empty_state)
        _run_git(
            ["fsck", "--full"],
            directory=repository,
            environment=environment,
            heartbeat=heartbeat,
        )
        refs: bytes = _run_git(
            ["for-each-ref", "--format=%(refname) %(objectname)"],
            directory=repository,
            environment=environment,
            heartbeat=heartbeat,
        )
        # Remove the service remote while retaining the repository's object
        # format/extensions (including SHA-256 repositories when supported).
        if not refs and (repository / "HEAD").read_text().startswith("ref: "):
            if source.has_recorded_history:
                raise SourceUnavailableError(
                    "The Git repository is empty despite recorded project history."
                )
            shutil.rmtree(repository)
            return GitMirrorResult(refs={}, state="empty")
        captured_refs: dict[str, str] = dict(
            line.split(" ", 1) for line in refs.decode("utf-8").splitlines()
        )
        candidates: list[str] = [
            "HEAD",
            *sorted(
                captured_refs,
                key=lambda ref: (
                    not ref.startswith("refs/heads/"),
                    not ref.startswith("refs/tags/"),
                    ref,
                ),
            ),
        ]
        selected_ref: str = ""
        checkout_commit: str = ""
        for candidate in candidates:
            checkout_commit = (
                _run_git(
                    ["rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"],
                    directory=repository,
                    environment=environment,
                    heartbeat=heartbeat,
                    expected_exit_codes=(0, 1),
                )
                .decode("ascii")
                .strip()
            )
            if checkout_commit:
                selected_ref = candidate
                break
        if not checkout_commit:
            raise SourceUnavailableError("The Git repository has no readable commit.")
        checkout: list[str] = (
            ["reset", "--hard", "HEAD"]
            if selected_ref == "HEAD"
            else ["checkout", "--detach", checkout_commit]
        )
        for arguments in (
            ["config", "--local", "--remove-section", "remote.origin"],
            ["config", "--local", "core.bare", "false"],
            # Store link targets as regular files. Git retains original symlink
            # objects, and neither checkout nor ZIP writing follows their targets.
            ["config", "--local", "core.symlinks", "false"],
            [
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "submodule.recurse=false",
                *checkout,
            ],
        ):
            _run_git(
                arguments,
                directory=destination,
                environment=environment,
                heartbeat=heartbeat,
            )
        return GitMirrorResult(
            refs=captured_refs,
            state="mirrored",
            checkout_commit=checkout_commit,
            used_fallback_head=selected_ref != "HEAD",
        )


def _count_gpx_positions(document: Any) -> int:
    """Bound converter allocations before constructing gpxpy point objects."""
    if not isinstance(document, dict) or not isinstance(document.get("features"), list):
        raise SourceUnavailableError("Stored GPS GeoJSON is invalid; GPX was omitted.")
    count: int = 0
    for feature in document["features"]:
        geometry: Any = feature.get("geometry") if isinstance(feature, dict) else None
        if not isinstance(geometry, dict):
            raise SourceUnavailableError(
                "Stored GPS GeoJSON is invalid; GPX was omitted."
            )
        coordinates: Any = geometry.get("coordinates")
        if not isinstance(coordinates, list):
            raise SourceUnavailableError(
                "Stored GPS GeoJSON is invalid; GPX was omitted."
            )
        if geometry.get("type") == "LineString":
            count += len(coordinates)
        elif geometry.get("type") == "MultiLineString":
            for line in coordinates:
                if not isinstance(line, list):
                    raise SourceUnavailableError(
                        "Stored GPS GeoJSON is invalid; GPX was omitted."
                    )
                count += len(line)
        else:
            raise SourceUnavailableError(
                "Stored GPS GeoJSON is invalid; GPX was omitted."
            )
    return count


def derive_gpx(source: Path, destination: Path, *, name: str) -> None:
    byte_limit: int = int(
        getattr(settings, "EXPORT_GPX_MAX_BYTES", MAX_GPX_INPUT_BYTES)
    )
    position_limit: int = int(
        getattr(settings, "EXPORT_GPX_MAX_POSITIONS", MAX_GPX_POSITIONS)
    )
    if source.stat().st_size > byte_limit:
        raise SourceUnavailableError(
            "GPX conversion input limit exceeded; GeoJSON retained."
        )
    try:
        document: Any = orjson.loads(source.read_bytes())
        if _count_gpx_positions(document) > position_limit:
            raise SourceUnavailableError(
                "GPX conversion position limit exceeded; GeoJSON retained."
            )
        gpx = gps_track_geojson_to_gpx(document, track_name=name)
        destination.write_text(gpx.to_xml(version=GPX_VERSION), encoding="utf-8")
    except orjson.JSONDecodeError, InvalidGPSTrackGeoJSONError:
        raise SourceUnavailableError(
            "Stored GPS GeoJSON is invalid; GPX was omitted."
        ) from None
