"""Run production browser upload modules against Django and real object storage."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.test import Client
from django.urls import reverse

from speleodb.gis.models import GISLayer

if TYPE_CHECKING:
    from pytest_django.live_server_helper import LiveServer

    from speleodb.users.models import User

BASE_DIR: Path = Path(__file__).resolve().parents[4]


@pytest.mark.django_db(transaction=True)
def test_browser_uploads_use_real_django_and_storage(
    live_server: LiveServer, user: User
) -> None:
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    client: Client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    # Only a database-backed session is prepared in-process. The HTML, CSRF
    # cookie, list requests and uploads all travel over the actual live server.
    browser_configuration: dict[str, Any] = {
        "url": f"{live_server.url}{reverse('private:gis_layers')}",
        "sessionCookie": {
            "name": settings.SESSION_COOKIE_NAME,
            "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
        },
    }
    node: str | None = shutil.which("node")
    assert node is not None, "Node.js is required for real browser upload tests"
    try:
        with socket.socket() as unavailable:
            unavailable.bind(("127.0.0.1", 0))
            browser_configuration["unavailableUrl"] = (
                f"http://127.0.0.1:{unavailable.getsockname()[1]}/upload"
            )
            result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603 - fixed script, private stdin
                [node, "scripts/test-frontend-uploads.mjs"],
                cwd=BASE_DIR,
                input=json.dumps(browser_configuration),
                capture_output=True,
                text=True,
                check=False,
                timeout=90,
            )
        assert result.returncode == 0, result.stderr
        report: dict[str, Any] = json.loads(result.stdout)
        assert report["checks"] == [
            "gis-modal",
            "gis-upload-and-refresh",
            "gis-server-validation",
            "upload-helper-success-and-progress",
            "upload-helper-custom-method",
            "upload-helper-csrf",
            "upload-helper-empty-response",
            "upload-helper-html-response",
            "upload-helper-server-error",
            "upload-helper-network-error",
            "upload-controller-success",
            "upload-controller-rejection",
            "upload-controller-cancellation",
        ]
        layers = GISLayer.objects.filter(created_by=user.email)
        assert layers.count() == 3  # noqa: PLR2004
        for source in report["stored"]:
            layer: GISLayer = layers.get(id=source["id"])
            assert layer.name == source["name"]
            assert layer.source_f.name == layer.data_f.name
            # This reads back from the configured real S3-compatible service.
            with layer.source_f.open("rb") as stored_file:
                assert stored_file.read() == source["contents"].encode()
    finally:
        deleted_files: set[tuple[int, str]] = set()
        for layer in GISLayer.objects.filter(created_by=user.email):
            for field in (layer.source_f, layer.data_f):
                if field.name:
                    stored_file_key: tuple[int, str] = (id(field.storage), field.name)
                    if stored_file_key not in deleted_files:
                        field.delete(save=False)
                        deleted_files.add(stored_file_key)
