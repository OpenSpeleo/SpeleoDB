"""Real database and attachment storage for the rendered resource edit forms."""

from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
from typing import TYPE_CHECKING
from typing import Final

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.uploadedfile import UploadedFile
from django.core.files.uploadhandler import MemoryFileUploadHandler
from django.http.multipartparser import MultiPartParser

from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import StationResourceType
from speleodb.gis.models import StationResource
from speleodb.gis.models import SurfaceMonitoringNetwork
from speleodb.gis.models import SurfaceMonitoringNetworkUserPermission
from speleodb.gis.models import SurfaceStation
from speleodb.utils.s3_storages import AttachmentStorage

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Generator

    from django.core.files.storage import Storage
    from django.http import HttpRequest
    from django.http import HttpResponse

    from speleodb.users.models import User


_resource_patch_bodies: dict[str, list[tuple[str, bytes]]] = {}
_RESOURCE_PATCH_BODY_LIMIT: Final[int] = 16 * 1024


class ResourcePatchCaptureMiddleware:
    """Observe fixture-owned uploads that browser debug protocols omit."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        captured: list[tuple[str, bytes]] | None = _resource_patch_bodies.get(
            request.path
        )
        observe: bool = request.method == "PATCH" and captured is not None
        if observe:
            assert (
                int(request.headers.get("content-length", "0"))
                <= _RESOURCE_PATCH_BODY_LIMIT
            )
            # The supported body property preserves Django's cached body/stream
            # for the unmodified production handler. Never record credentials.
            body: bytes = request.body
            assert len(body) <= _RESOURCE_PATCH_BODY_LIMIT
            assert captured is not None
            captured.append((request.headers.get("Content-Type", ""), body))
        response: HttpResponse = self.get_response(request)
        if observe:
            # Prove the browser's successful request was actually observed.
            response["X-SpeleoDB-Test-Resource-Patch"] = request.path
        return response


def assert_resource_patches(records: dict[str, dict[str, str]]) -> None:
    """Check actual multipart bytes without depending on browser file capture."""
    for browser_records in records.values():
        captures: dict[str, list[tuple[str, bytes]]] = {
            kind: _resource_patch_bodies[f"/api/v2/resources/{browser_records[kind]}/"]
            for kind in ("note", "document")
        }
        # An unrelated focused browser workload never opens this resource form.
        if not any(captures.values()):
            continue
        for kind, bodies in captures.items():
            assert len(bodies) == 1, (
                f"Expected one {kind} PATCH, received {len(bodies)}"
            )
            content_type, body = bodies[0]
            data, files = MultiPartParser(
                {"CONTENT_TYPE": content_type, "CONTENT_LENGTH": str(len(body))},
                BytesIO(body),
                [MemoryFileUploadHandler()],
                encoding="utf-8",
            ).parse()
            try:
                expected_fields: set[str] = {"title", "description"}
                if kind == "note":
                    expected_fields.add("text_content")
                assert set(data) == expected_fields
                assert "resource_type" not in data
                assert "resource_type" not in files
                assert data["title"] == f"Updated {kind}"
                assert data["description"] == ""
                if kind == "note":
                    assert data["text_content"] == "Updated note café 🦇"
                    assert not files
                else:
                    assert "text_content" not in data
                    assert set(files) == {"file"}
                    uploaded = files["file"]
                    assert isinstance(uploaded, UploadedFile)
                    assert uploaded.name == "replacement.txt"
                    assert uploaded.content_type == "text/plain"
                    assert uploaded.read() == "Replacement café 🦇".encode()
            finally:
                for _, uploaded_files in files.lists():
                    for uploaded in uploaded_files:
                        uploaded.close()


@contextmanager
def resource_edit_records(user: User) -> Generator[dict[str, dict[str, str]]]:
    """Give each engine fresh rows and remove only this network's uploaded keys."""
    network: SurfaceMonitoringNetwork = SurfaceMonitoringNetwork.objects.create(
        name="Browser resource edits", created_by=user.email
    )
    SurfaceMonitoringNetworkUserPermission.objects.create(
        network=network, user=user, level=PermissionLevel.ADMIN
    )
    resources: list[StationResource] = []
    records: dict[str, dict[str, str]] = {}
    try:
        for browser in ("chromium", "webkit"):
            station: SurfaceStation = SurfaceStation.objects.create(
                network=network,
                name=f"Resource station {browser}",
                latitude="20.0050000",
                longitude="-86.9900000",
                created_by=user.email,
            )
            note: StationResource = StationResource(
                station=station,
                resource_type=StationResourceType.NOTE,
                title="Original note",
                description="Original description",
                text_content="Original note text",
                created_by=user.email,
            )
            resources.append(note)
            note.save()
            document: StationResource = StationResource(
                station=station,
                resource_type=StationResourceType.DOCUMENT,
                title="Original document",
                description="Original description",
                file=SimpleUploadedFile(
                    "original.txt",
                    b"Original document bytes",
                    content_type="text/plain",
                ),
                created_by=user.email,
            )
            resources.append(document)
            document.save()
            records[browser] = {
                "station": str(station.id),
                "note": str(note.id),
                "document": str(document.id),
            }
            for resource in (note, document):
                _resource_patch_bodies[f"/api/v2/resources/{resource.id}/"] = []
        yield records
        assert_resource_patches(records)
    finally:
        for browser_records in records.values():
            for kind in ("note", "document"):
                _resource_patch_bodies.pop(
                    f"/api/v2/resources/{browser_records[kind]}/", None
                )
        # The original objects retain replaced file names. Fresh rows include
        # browser uploads, including writes made before an assertion failed.
        persisted = StationResource.objects.filter(
            id__in=[item.id for item in resources]
        )
        keys: set[str] = set()
        owned_prefix: str = f"networks/{network.id}/"
        for resource in [*resources, *persisted]:
            for file in (resource.file, resource.miniature):
                if file.name and file.name.startswith(owned_prefix):
                    keys.add(file.name)
        storage: Storage = AttachmentStorage()
        for key in keys:
            storage.delete(key)
        network.delete()
